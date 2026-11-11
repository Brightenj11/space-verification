// PMSteppingAction.cc 
#include "PMSteppingAction.hh"
#include "PMRunAction.hh"
#include "PMPrimaryGenerator.hh"

#include "G4AnalysisManager.hh"
#include "G4EventManager.hh"
#include "G4Event.hh"
#include "G4Gamma.hh"
#include "G4Neutron.hh"
#include "G4Proton.hh"
#include "G4RunManager.hh"
#include "G4Step.hh"
#include "G4StepPoint.hh"
#include "G4StepStatus.hh"
#include "G4SystemOfUnits.hh"
#include "G4Track.hh"
#include "G4VProcess.hh"
#include "G4ProcessType.hh"
#include "G4ParticleDefinition.hh"
#include "G4IonTable.hh"
#include "G4GenericMessenger.hh"
#include "G4String.hh"

#include <string>
#include <unordered_set>
#include <unordered_map>

G4double PMSteppingAction::sMaxEventTime_ns          = 1e8;
G4bool   PMSteppingAction::sKillGammas              = true;

// For your current objective, this MUST default false (or you will never see escapes)
G4bool   PMSteppingAction::sKillNeutronsAfterRecord = false;

// Must stay false for ScoringPanel tallies: a neutron killed at escape never reaches a panel.
G4bool   PMSteppingAction::sKillNeutronsAfterEscape = false;

thread_local int    PMSteppingAction::t_evtId                = -1;

thread_local bool   PMSteppingAction::t_seenPrimaryInelastic = false;
thread_local bool   PMSteppingAction::t_primaryHitBus        = false;
thread_local int    PMSteppingAction::t_vtxRegion            = 99;
thread_local double PMSteppingAction::t_EpVtx_MeV            = 0.0;
thread_local double PMSteppingAction::t_tVtx_ns              = 0.0;

thread_local G4String PMSteppingAction::t_vtxProcName         = "";
thread_local int      PMSteppingAction::t_vtxProcType         = -1;
thread_local int      PMSteppingAction::t_vtxProcSubType      = -1;

thread_local int    PMSteppingAction::t_nFissionsSNM         = 0;
thread_local double PMSteppingAction::t_tFirstFission_ns     = -1.0;

thread_local std::array<int,6> PMSteppingAction::t_nBornByReg    = {0,0,0,0,0,0};
thread_local std::array<int,6> PMSteppingAction::t_nEscByBirthReg= {0,0,0,0,0,0};
thread_local std::array<int,2> PMSteppingAction::t_nPanelHits    = {0,0};

thread_local std::unordered_map<int, PMSteppingAction::BirthInfo> PMSteppingAction::t_birth;
thread_local std::unordered_set<int> PMSteppingAction::t_escaped;

PMSteppingAction::PMSteppingAction(PMRunAction* runAction)
: fRunAction(runAction) {
  BuildMessenger();
}

PMSteppingAction::~PMSteppingAction() {
  delete fMessenger;
  fMessenger = nullptr;
}

void PMSteppingAction::BuildMessenger() {
  fMessenger = new G4GenericMessenger(this, "/pm/", "PM controls (escape-focused tallying)");
  fMessenger->DeclarePropertyWithUnit("maxEventTime","ns", sMaxEventTime_ns)
            .SetGuidance("Terminate tracks after this global time (ns) to bound runtime.");
  fMessenger->DeclareProperty("killGammas", sKillGammas)
            .SetGuidance("Kill gamma tracks immediately (declutter).");
  fMessenger->DeclareProperty("killNeutronsAfterRecord", sKillNeutronsAfterRecord)
            .SetGuidance("DEBUG ONLY: kill neutron at birth record (prevents escape tally).");
  fMessenger->DeclareProperty("killNeutronsAfterEscape", sKillNeutronsAfterEscape)
            .SetGuidance("Kill neutrons after they cross into WorldLV (speedup; true disables ScoringPanel hits).");
}

int PMSteppingAction::RegionCodeFromLVName(const G4String& lvName) {
  // Your declared convention:
  // 0=outside bus vacuum, 1=hull, 2=inside-bus vacuum, 4=SNM shell, 5=SNM core vacuum
  // (3 was the electronics payload box, now removed; code kept unused so 4/5 don't shift)
  if (lvName == "WorldLV")          return 0;
  if (lvName == "BusShellLV")       return 1;
  if (lvName == "BusEnvelopeLV")    return 2;
  if (lvName == "SNMSphereLV")      return 4;
  if (lvName == "SNMCoreLV")        return 5;
  return 99;
}

int PMSteppingAction::RegionCodeAtPoint(const G4StepPoint* p) {
  if (!p) return 99;
  const auto* pv = p->GetPhysicalVolume();
  if (!pv) return 99;
  const auto* lv = pv->GetLogicalVolume();
  if (!lv) return 99;
  return RegionCodeFromLVName(lv->GetName());
}

G4String PMSteppingAction::RegionNameFromCode(int code) {
  switch (code) {
    case 0:  return "World";
    case 1:  return "BusShell";
    case 2:  return "BusEnvelope";
    case 4:  return "SNMSphere";
    case 5:  return "SNMCore";
    default: return "Unknown";
  }
}

G4String PMSteppingAction::SanitizeForCSV(const G4String& s) {
  // Conservative sanitization: keep ASCII printable, avoid commas/newlines.
  // (CSV backends often handle quoting, but this prevents surprises.)
  G4String out;
  out.reserve(s.size());
  for (char c : s) {
    if (c == ',') { out.push_back(';'); continue; }
    if (c == '\n' || c == '\r' || c == '\t') { out.push_back(' '); continue; }
    // Drop non-printable control chars
    if (static_cast<unsigned char>(c) < 32) continue;
    out.push_back(c);
  }
  return out;
}

G4String PMSteppingAction::CreatorCategory(const G4VProcess* proc) {
  const G4String name = proc ? proc->GetProcessName() : "";
  if (name.empty()) return "none";

  // Common creator processes you are likely to care about with *_HP physics.
  if (name == "RadioactiveDecay") return "RadioactiveDecay";
  if (name == "nFission" || name.find("Fission") != std::string::npos) return "Fission";
  if (name == "nCapture" || name.find("Capture") != std::string::npos) return "Capture";

  // De-excitation / evaporation / photon evaporation
  if (name == "PhotonEvaporation" || name == "nuclearDeexcitation" ||
      name.find("Evaporation")   != std::string::npos ||
      name.find("Deexcitation") != std::string::npos)
    return "Deexcitation";

  if (name.find("Inelastic") != std::string::npos) return "Inelastic";
  if (name.find("Elastic")   != std::string::npos) return "Elastic";

  return "Other";
}

int PMSteppingAction::CreatorCode(const G4VProcess* proc) {
  // Keep legacy codes (0..3) but extend with a few high-value codes.
  // 0=Other/Unknown, 1=RadioactiveDecay, 2=Deexcitation/Evaporation,
  // 3=Inelastic, 4=Fission, 5=Capture, 6=Elastic
  const G4String cat = CreatorCategory(proc);
  if (cat == "RadioactiveDecay") return 1;
  if (cat == "Deexcitation")     return 2;
  if (cat == "Inelastic")        return 3;
  if (cat == "Fission")          return 4;
  if (cat == "Capture")          return 5;
  if (cat == "Elastic")          return 6;
  return 0;
}

void PMSteppingAction::ResetEventStateIfNew(int eid) {
  if (eid == t_evtId) return;

  t_evtId = eid;

  t_seenPrimaryInelastic = false;
  t_primaryHitBus        = false;
  t_vtxRegion            = 99;
  t_EpVtx_MeV            = 0.0;
  t_tVtx_ns              = 0.0;

  t_vtxProcName           = "";
  t_vtxProcType           = -1;
  t_vtxProcSubType        = -1;

  t_nFissionsSNM         = 0;
  t_tFirstFission_ns     = -1.0;

  t_nBornByReg.fill(0);
  t_nEscByBirthReg.fill(0);
  t_nPanelHits.fill(0);

  t_birth.clear();
  t_escaped.clear();
}

void PMSteppingAction::DetectSNMFissionLike(const G4Step* step, int preRegion) {
  // Only count "fission-like" events occurring in SNM shell material
  if (preRegion != 4) return;

  const auto* secs = step->GetSecondaryInCurrentStep();
  if (!secs || secs->empty()) return;

  int heavyCount = 0;
  for (const auto* sec : *secs) {
    const auto* def = sec->GetDefinition();
    if (!def) continue;

    if (def->GetParticleType() == "nucleus" || def->GetParticleType() == "ion") {
      const int A = def->GetAtomicMass();
      if (A >= 70) heavyCount++;
    }
  }

  // Require at least two heavy fragments to reduce false positives from single heavy residues
  if (heavyCount < 2) return;

  t_nFissionsSNM += 1;
  if (t_tFirstFission_ns < 0.0) {
    const auto* post = step->GetPostStepPoint();
    t_tFirstFission_ns = post ? post->GetGlobalTime()/ns : -1.0;
  }
}

void PMSteppingAction::WriteEventsRow() {
  auto* ana = G4AnalysisManager::Instance();
  const int id = fRunAction->EventsId();

  int nBornTotal = 0;
  int nEscTotal  = 0;
  for (int i=0; i<6; ++i) {
    nBornTotal += t_nBornByReg[i];
    nEscTotal  += t_nEscByBirthReg[i];
  }

  int cls = 0;
  if (t_nFissionsSNM > 0) cls = 2;
  else if (t_seenPrimaryInelastic) cls = 1;

  ana->FillNtupleIColumn(id, PMRunAction::kEvt_eventID, t_evtId);
  ana->FillNtupleIColumn(id, PMRunAction::kEvt_class, cls);
  ana->FillNtupleIColumn(id, PMRunAction::kEvt_vtxRegion, t_vtxRegion);
  ana->FillNtupleDColumn(id, PMRunAction::kEvt_EpVtx_MeV, t_EpVtx_MeV);
  ana->FillNtupleDColumn(id, PMRunAction::kEvt_t_vertex_ns, t_tVtx_ns);
  ana->FillNtupleIColumn(id, PMRunAction::kEvt_nFissionsSNM, t_nFissionsSNM);
  ana->FillNtupleDColumn(id, PMRunAction::kEvt_t_firstFission_ns, t_tFirstFission_ns);

  ana->FillNtupleIColumn(id, PMRunAction::kEvt_nBornTotal, nBornTotal);
  ana->FillNtupleIColumn(id, PMRunAction::kEvt_nBorn_r0, t_nBornByReg[0]);
  ana->FillNtupleIColumn(id, PMRunAction::kEvt_nBorn_r1, t_nBornByReg[1]);
  ana->FillNtupleIColumn(id, PMRunAction::kEvt_nBorn_r2, t_nBornByReg[2]);
  ana->FillNtupleIColumn(id, PMRunAction::kEvt_nBorn_r4, t_nBornByReg[4]);
  ana->FillNtupleIColumn(id, PMRunAction::kEvt_nBorn_r5, t_nBornByReg[5]);

  ana->FillNtupleIColumn(id, PMRunAction::kEvt_nEscapedTotal, nEscTotal);
  ana->FillNtupleIColumn(id, PMRunAction::kEvt_nEscBirth_r0, t_nEscByBirthReg[0]);
  ana->FillNtupleIColumn(id, PMRunAction::kEvt_nEscBirth_r1, t_nEscByBirthReg[1]);
  ana->FillNtupleIColumn(id, PMRunAction::kEvt_nEscBirth_r2, t_nEscByBirthReg[2]);
  ana->FillNtupleIColumn(id, PMRunAction::kEvt_nEscBirth_r4, t_nEscByBirthReg[4]);
  ana->FillNtupleIColumn(id, PMRunAction::kEvt_nEscBirth_r5, t_nEscByBirthReg[5]);

  // ---- Human-readable helpers (makes validation/debugging much easier) ----
  const int hasInelastic = t_seenPrimaryInelastic ? 1 : 0;
  const int hasFissionLike = (t_nFissionsSNM > 0) ? 1 : 0;

  const G4String classLabel = hasFissionLike ? "snmFissionLike"
                                             : (hasInelastic ? "primaryHadronic" : "none");
  const G4String vtxRegLabel = (t_vtxRegion == 99) ? "none" : RegionNameFromCode(t_vtxRegion);
  const G4String vtxProcLabel = t_vtxProcName.empty() ? "none" : t_vtxProcName;

  ana->FillNtupleIColumn(id, PMRunAction::kEvt_hasPrimaryInelastic, hasInelastic);
  ana->FillNtupleIColumn(id, PMRunAction::kEvt_hasSNMFissionLike, hasFissionLike);
  ana->FillNtupleSColumn(id, PMRunAction::kEvt_classLabel, classLabel);
  ana->FillNtupleSColumn(id, PMRunAction::kEvt_vtxRegionName, vtxRegLabel);
  ana->FillNtupleSColumn(id, PMRunAction::kEvt_vtxProcName, vtxProcLabel);
  ana->FillNtupleIColumn(id, PMRunAction::kEvt_vtxProcType, t_vtxProcType);
  ana->FillNtupleIColumn(id, PMRunAction::kEvt_vtxProcSubType, t_vtxProcSubType);
  const auto* gen = static_cast<const PMPrimaryGenerator*>(
      G4RunManager::GetRunManager()->GetUserPrimaryGeneratorAction());
  ana->FillNtupleDColumn(id, PMRunAction::kEvt_pitch_deg, gen ? gen->GetLastPitchDeg() : -1.0);
  ana->FillNtupleIColumn(id, PMRunAction::kEvt_hitBus, t_primaryHitBus ? 1 : 0);
  ana->FillNtupleDColumn(id, PMRunAction::kEvt_E_primary_MeV, gen ? gen->GetEnergy()/MeV : -1.0);
  ana->FillNtupleIColumn(id, PMRunAction::kEvt_nHitDownstream, t_nPanelHits[0]);
  ana->FillNtupleIColumn(id, PMRunAction::kEvt_nHitTransverse, t_nPanelHits[1]);

  ana->AddNtupleRow(id);
}

void PMSteppingAction::EndOfEvent() {
  if (t_evtId < 0) return;
  WriteEventsRow();

  // Make sure next event starts clean even if no steps happen before reset
  t_evtId = -1;
  t_birth.clear();
  t_escaped.clear();
}

void PMSteppingAction::UserSteppingAction(const G4Step* step) {
  const auto* ev = G4EventManager::GetEventManager()->GetConstCurrentEvent();
  const int eid  = ev ? ev->GetEventID() : -1;
  ResetEventStateIfNew(eid);

  const auto* track = step->GetTrack();
  const auto* def   = track ? track->GetDefinition() : nullptr;
  if (!def) return;

  const auto* pre   = step->GetPreStepPoint();
  const auto* post  = step->GetPostStepPoint();

  const int preReg  = RegionCodeAtPoint(pre);
  const int postReg = RegionCodeAtPoint(post);

  const double tg_ns = post ? post->GetGlobalTime()/ns : 0.0;

  // Bound runtime
  if (tg_ns > sMaxEventTime_ns) {
    const_cast<G4Track*>(track)->SetTrackStatus(fStopAndKill);
    return;
  }

  // Kill gammas if enabled
  if (sKillGammas && def == G4Gamma::Definition()) {
    const_cast<G4Track*>(track)->SetTrackStatus(fStopAndKill);
    return;
  }

  // Primary proton: latch first hadronic inelastic / secondary-producing vertex and region
  if (def->GetParticleName() == "proton" && track->GetParentID() == 0) {
    if (postReg >= 1 && postReg <= 5) t_primaryHitBus = true; // entered bus or anything inside it

    const auto* proc = post ? post->GetProcessDefinedStep() : nullptr;
    const bool isHadronic = (proc && proc->GetProcessType() == fHadronic);

    bool hasSecondaries = false;
    if (const auto* secs = step->GetSecondaryInCurrentStep()) {
      hasSecondaries = !secs->empty();
    }

    const G4String procName = proc ? proc->GetProcessName() : "";
    const bool nameSaysInelastic = (procName.find("Inelastic") != std::string::npos);

    if (!t_seenPrimaryInelastic && isHadronic && (nameSaysInelastic || hasSecondaries)) {
      t_seenPrimaryInelastic = true;
      t_vtxRegion = preReg;
      t_EpVtx_MeV = pre ? pre->GetKineticEnergy()/MeV : 0.0;
      t_tVtx_ns   = post ? post->GetGlobalTime()/ns : 0.0;

      // Debug: store what Geant4 actually thinks defined the step.
      // This is the most direct way to catch misclassification from name-matching.
      t_vtxProcName    = SanitizeForCSV(procName);
      t_vtxProcType    = proc ? static_cast<int>(proc->GetProcessType())    : -1;
      t_vtxProcSubType = proc ? static_cast<int>(proc->GetProcessSubType()) : -1;
    }
  }

  // Count SNM fission-like events (any projectile) but only in SNM shell region
  DetectSNMFissionLike(step, preReg);

  // Neutron birth: record birth region and save birth info for later escape attribution
  if (def == G4Neutron::Definition() && track->GetCurrentStepNumber() == 1) {
    BirthInfo bi;
    bi.region  = preReg;
    bi.E_MeV   = (pre ? pre->GetKineticEnergy()/MeV : track->GetKineticEnergy()/MeV);
    bi.t_ns    = (post ? post->GetGlobalTime()/ns : 0.0);
    const auto* cproc = track->GetCreatorProcess();
    bi.creatorProcName = SanitizeForCSV(cproc ? cproc->GetProcessName() : "primary");
    bi.creatorCategory = CreatorCategory(cproc);
    bi.creatorType     = cproc ? static_cast<int>(cproc->GetProcessType())    : -1;
    bi.creatorSubType  = cproc ? static_cast<int>(cproc->GetProcessSubType()) : -1;
    bi.creator         = CreatorCode(cproc);

    t_birth[track->GetTrackID()] = bi;

    if (bi.region >= 0 && bi.region <= 5) t_nBornByReg[bi.region] += 1;

    if (sKillNeutronsAfterRecord) {
      const_cast<G4Track*>(track)->SetTrackStatus(fStopAndKill);
      return;
    }
  }

  // Neutron escape: detect crossing into WorldLV (region 0) from hull (1) or inside vacuum (2)
  if (def == G4Neutron::Definition() && post && post->GetStepStatus() == fGeomBoundary) {
    if (postReg == 0 && (preReg == 1 || preReg == 2)) {
      const int tid = track->GetTrackID();
      if (t_escaped.insert(tid).second) {
        // first time we've counted this neutron escaping
        BirthInfo bi;
        auto it = t_birth.find(tid);
        if (it != t_birth.end()) bi = it->second;

        if (bi.region >= 0 && bi.region <= 5) t_nEscByBirthReg[bi.region] += 1;

        auto* ana = G4AnalysisManager::Instance();
        const int nid = fRunAction->EscapesId();

        ana->FillNtupleIColumn(nid, PMRunAction::kEsc_eventID, t_evtId);
        ana->FillNtupleIColumn(nid, PMRunAction::kEsc_trackID, tid);
        ana->FillNtupleIColumn(nid, PMRunAction::kEsc_birthRegion, bi.region);
        ana->FillNtupleDColumn(nid, PMRunAction::kEsc_birthE_MeV, bi.E_MeV);
        ana->FillNtupleDColumn(nid, PMRunAction::kEsc_birthT_ns, bi.t_ns);
        ana->FillNtupleIColumn(nid, PMRunAction::kEsc_creatorCode, bi.creator);

        ana->FillNtupleDColumn(nid, PMRunAction::kEsc_escapeE_MeV, post->GetKineticEnergy()/MeV);
        ana->FillNtupleDColumn(nid, PMRunAction::kEsc_escapeT_ns, post->GetGlobalTime()/ns);

        const auto dir = post->GetMomentumDirection();
        ana->FillNtupleDColumn(nid, PMRunAction::kEsc_dirX, dir.x());
        ana->FillNtupleDColumn(nid, PMRunAction::kEsc_dirY, dir.y());
        ana->FillNtupleDColumn(nid, PMRunAction::kEsc_dirZ, dir.z());

        const auto pos = post->GetPosition();
        ana->FillNtupleDColumn(nid, PMRunAction::kEsc_posX, pos.x()/mm);
        ana->FillNtupleDColumn(nid, PMRunAction::kEsc_posY, pos.y()/mm);
        ana->FillNtupleDColumn(nid, PMRunAction::kEsc_posZ, pos.z()/mm);

        // ---- Human-readable creator details (debug) ----
        ana->FillNtupleSColumn(nid, PMRunAction::kEsc_creatorProcName, bi.creatorProcName);
        ana->FillNtupleSColumn(nid, PMRunAction::kEsc_creatorCategory, bi.creatorCategory);
        ana->FillNtupleIColumn(nid, PMRunAction::kEsc_creatorType, bi.creatorType);
        ana->FillNtupleIColumn(nid, PMRunAction::kEsc_creatorSubType, bi.creatorSubType);

        ana->AddNtupleRow(nid);

        if (sKillNeutronsAfterEscape) {
          const_cast<G4Track*>(track)->SetTrackStatus(fStopAndKill);
          return;
        }
      }
    }
  }

  // Neutron entering a ScoringPanel (copy 0 = downstream +x, copy 1 = transverse +z).
  // ponytail: counts every entry; panels are vacuum so a track can't re-enter. Dedupe per
  // (trackID, panel) if the panels get a scattering material.
  if (def == G4Neutron::Definition() && post && post->GetStepStatus() == fGeomBoundary) {
    const auto* pv = post->GetPhysicalVolume();
    if (pv && pv->GetLogicalVolume()->GetName() == "ScoringPanelLV") {
      const int panel = pv->GetCopyNo();
      if (panel == 0 || panel == 1) t_nPanelHits[panel] += 1;

      BirthInfo bi;
      auto it = t_birth.find(track->GetTrackID());
      if (it != t_birth.end()) bi = it->second;

      auto* ana = G4AnalysisManager::Instance();
      const int hid = fRunAction->PanelHitsId();
      const auto pos = post->GetPosition();
      const auto dir = post->GetMomentumDirection();
      ana->FillNtupleIColumn(hid, PMRunAction::kHit_eventID, t_evtId);
      ana->FillNtupleIColumn(hid, PMRunAction::kHit_trackID, track->GetTrackID());
      ana->FillNtupleIColumn(hid, PMRunAction::kHit_panel, panel);
      ana->FillNtupleDColumn(hid, PMRunAction::kHit_E_MeV, post->GetKineticEnergy()/MeV);
      ana->FillNtupleDColumn(hid, PMRunAction::kHit_t_ns, post->GetGlobalTime()/ns);
      ana->FillNtupleDColumn(hid, PMRunAction::kHit_posX, pos.x()/mm);
      ana->FillNtupleDColumn(hid, PMRunAction::kHit_posY, pos.y()/mm);
      ana->FillNtupleDColumn(hid, PMRunAction::kHit_posZ, pos.z()/mm);
      ana->FillNtupleDColumn(hid, PMRunAction::kHit_dirX, dir.x());
      ana->FillNtupleDColumn(hid, PMRunAction::kHit_dirY, dir.y());
      ana->FillNtupleDColumn(hid, PMRunAction::kHit_dirZ, dir.z());
      ana->FillNtupleIColumn(hid, PMRunAction::kHit_birthRegion, bi.region);
      ana->FillNtupleDColumn(hid, PMRunAction::kHit_birthE_MeV, bi.E_MeV);
      ana->FillNtupleIColumn(hid, PMRunAction::kHit_creatorCode, bi.creator);
      ana->AddNtupleRow(hid);
    }
  }
}

// PMSteppingAction.cc
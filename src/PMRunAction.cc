// PMRunAction.cc
#include "PMRunAction.hh"

#include "G4AnalysisManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4Threading.hh"
#include "G4RunManager.hh"
#include "G4VModularPhysicsList.hh"
#include "G4ios.hh"

#include "PMDetectorConstruction.hh"
#include "PMPrimaryGenerator.hh"

PMRunAction::PMRunAction(const G4String& physName)
: fPhysNameRequested(physName) {
  auto* ana = G4AnalysisManager::Instance();
  ana->SetVerboseLevel(1);
  ana->SetNtupleMerging(true);
  ana->SetDefaultFileType("root");

  SetupOutput();  // define ntuples/columns once per thread
}

PMRunAction::~PMRunAction() {}

void PMRunAction::BeginOfRunAction(const G4Run* run) {
  auto* ana = G4AnalysisManager::Instance();
  if (ana->GetFileName().empty() || ana->GetFileName()=="g4" || ana->GetFileName()=="G4") {
    ana->SetFileName("proton_output");
  }
  ana->OpenFile();

  // ---- Fill RunConfig ONCE ----
  // In MT, the master thread does NOT have PMPrimaryGenerator (your BuildForMaster sets only PMRunAction).
  // So: fill on worker thread 0. In sequential mode, fill on master.
  bool doFill = false;
  if (G4Threading::IsMasterThread()) {
    // sequential mode => generator exists on master
    doFill = (G4RunManager::GetRunManager()->GetUserPrimaryGeneratorAction() != nullptr);
  } else {
    doFill = (G4Threading::G4GetThreadId() == 0);
  }
  if (!doFill) return;

  auto* rm  = G4RunManager::GetRunManager();
  auto* det = static_cast<const PMDetectorConstruction*>(rm->GetUserDetectorConstruction());
  auto* gen = static_cast<const PMPrimaryGenerator*>(rm->GetUserPrimaryGeneratorAction());
  const auto* pl  = rm->GetUserPhysicsList();

  G4String plName = "UnknownPhysicsList";
  if (const auto* modular = dynamic_cast<const G4VModularPhysicsList*>(pl)) {
    plName = "G4VModularPhysicsList";
  }

  const int nid = fRunConfigNtupleId;

  ana->FillNtupleIColumn(nid, RunConfigCols::kCfg_runID, run ? run->GetRunID() : -1);
  // prefer requested name, fallback to whatever runtime string we could obtain
  const G4String physLabel = fPhysNameRequested.empty() ? plName : fPhysNameRequested;
  ana->FillNtupleSColumn(nid, RunConfigCols::kCfg_physicsListName, physLabel);

  if (det) {
    ana->FillNtupleSColumn(nid, RunConfigCols::kCfg_snmMaterial, det->GetSNMMaterialName());
    ana->FillNtupleDColumn(nid, RunConfigCols::kCfg_sphereOuterR_mm, det->GetSphereOuterRadius()/mm);
    ana->FillNtupleDColumn(nid, RunConfigCols::kCfg_sphereInnerR_mm, det->GetSphereInnerRadius()/mm);
  } else {
    ana->FillNtupleSColumn(nid, RunConfigCols::kCfg_snmMaterial, "UNKNOWN");
    ana->FillNtupleDColumn(nid, RunConfigCols::kCfg_sphereOuterR_mm, -1.0);
    ana->FillNtupleDColumn(nid, RunConfigCols::kCfg_sphereInnerR_mm, -1.0);
  }

  if (gen) {
    // Pitch-angle mode samples energy and direction every event: beamE is -1, beamDir is 0 0 0,
    // and pitchTable describes the source (per-event values are in Events).
    const bool pitchMode = !gen->GetPitchTable().empty();
    ana->FillNtupleSColumn(nid, RunConfigCols::kCfg_beamParticle, gen->GetParticleName());
    ana->FillNtupleDColumn(nid, RunConfigCols::kCfg_beamE_MeV, pitchMode ? -1.0 : gen->GetEnergy()/MeV);

    const auto dir = pitchMode ? G4ThreeVector() : gen->GetDirection();
    ana->FillNtupleDColumn(nid, RunConfigCols::kCfg_beamDirX, dir.x());
    ana->FillNtupleDColumn(nid, RunConfigCols::kCfg_beamDirY, dir.y());
    ana->FillNtupleDColumn(nid, RunConfigCols::kCfg_beamDirZ, dir.z());

    ana->FillNtupleSColumn(nid, RunConfigCols::kCfg_pitchTable, pitchMode ? gen->GetPitchTable() : G4String("none"));
  } else {
    ana->FillNtupleSColumn(nid, RunConfigCols::kCfg_beamParticle, "UNKNOWN");
    ana->FillNtupleDColumn(nid, RunConfigCols::kCfg_beamE_MeV, -1.0);
    ana->FillNtupleDColumn(nid, RunConfigCols::kCfg_beamDirX, 0.0);
    ana->FillNtupleDColumn(nid, RunConfigCols::kCfg_beamDirY, 0.0);
    ana->FillNtupleDColumn(nid, RunConfigCols::kCfg_beamDirZ, 0.0);
    ana->FillNtupleSColumn(nid, RunConfigCols::kCfg_pitchTable, "UNKNOWN");
  }

  ana->AddNtupleRow(nid);
}

void PMRunAction::EndOfRunAction(const G4Run*) {
  auto* ana = G4AnalysisManager::Instance();
  G4cout << "[PMRunAction] Writing & closing file.\n" << G4endl;
  ana->Write();
  ana->CloseFile();
}

void PMRunAction::SetupOutput() {
  auto* ana = G4AnalysisManager::Instance();

  // ---- RunConfig (one row per run) ----
  fRunConfigNtupleId = ana->CreateNtuple("RunConfig", "Run-level configuration metadata");
  ana->CreateNtupleIColumn(fRunConfigNtupleId, "runID");
  ana->CreateNtupleSColumn(fRunConfigNtupleId, "physicsListName");
  ana->CreateNtupleSColumn(fRunConfigNtupleId, "snmMaterial");
  ana->CreateNtupleDColumn(fRunConfigNtupleId, "sphereOuterR_mm");
  ana->CreateNtupleDColumn(fRunConfigNtupleId, "sphereInnerR_mm");
  ana->CreateNtupleSColumn(fRunConfigNtupleId, "beamParticle");
  ana->CreateNtupleDColumn(fRunConfigNtupleId, "beamE_MeV");
  ana->CreateNtupleDColumn(fRunConfigNtupleId, "beamDirX");
  ana->CreateNtupleDColumn(fRunConfigNtupleId, "beamDirY");
  ana->CreateNtupleDColumn(fRunConfigNtupleId, "beamDirZ");
  ana->CreateNtupleSColumn(fRunConfigNtupleId, "pitchTable");
  ana->FinishNtuple(fRunConfigNtupleId);

  // ---- Events (one row per event) ----
  fEventsNtupleId = ana->CreateNtuple("Events", "Per-event summary (escape-focused)");
  ana->CreateNtupleIColumn(fEventsNtupleId, "eventID");
  ana->CreateNtupleIColumn(fEventsNtupleId, "class");
  ana->CreateNtupleIColumn(fEventsNtupleId, "vtxRegion");
  ana->CreateNtupleDColumn(fEventsNtupleId, "E_p_at_vertex_MeV");
  ana->CreateNtupleDColumn(fEventsNtupleId, "t_vertex_ns");
  ana->CreateNtupleIColumn(fEventsNtupleId, "nFissionsSNM");
  ana->CreateNtupleDColumn(fEventsNtupleId, "t_firstFission_ns");

  ana->CreateNtupleIColumn(fEventsNtupleId, "nBornTotal");
  ana->CreateNtupleIColumn(fEventsNtupleId, "nBorn_r0");
  ana->CreateNtupleIColumn(fEventsNtupleId, "nBorn_r1");
  ana->CreateNtupleIColumn(fEventsNtupleId, "nBorn_r2");
  ana->CreateNtupleIColumn(fEventsNtupleId, "nBorn_r4");
  ana->CreateNtupleIColumn(fEventsNtupleId, "nBorn_r5");

  ana->CreateNtupleIColumn(fEventsNtupleId, "nEscapedTotal");
  ana->CreateNtupleIColumn(fEventsNtupleId, "nEscBirth_r0");
  ana->CreateNtupleIColumn(fEventsNtupleId, "nEscBirth_r1");
  ana->CreateNtupleIColumn(fEventsNtupleId, "nEscBirth_r2");
  ana->CreateNtupleIColumn(fEventsNtupleId, "nEscBirth_r4");
  ana->CreateNtupleIColumn(fEventsNtupleId, "nEscBirth_r5");

  // ---- Debug / human-readable helpers (optional, but very useful while validating classification) ----
  ana->CreateNtupleIColumn(fEventsNtupleId, "hasPrimaryInelastic");
  ana->CreateNtupleIColumn(fEventsNtupleId, "hasSNMFissionLike");
  ana->CreateNtupleSColumn(fEventsNtupleId, "classLabel");
  ana->CreateNtupleSColumn(fEventsNtupleId, "vtxRegionName");
  ana->CreateNtupleSColumn(fEventsNtupleId, "vtxProcessName");
  ana->CreateNtupleIColumn(fEventsNtupleId, "vtxProcessType");
  ana->CreateNtupleIColumn(fEventsNtupleId, "vtxProcessSubType");
  ana->CreateNtupleDColumn(fEventsNtupleId, "pitch_deg");
  ana->CreateNtupleIColumn(fEventsNtupleId, "hitBus");
  ana->CreateNtupleDColumn(fEventsNtupleId, "E_primary_MeV");
  ana->CreateNtupleIColumn(fEventsNtupleId, "nHitSide");
  ana->CreateNtupleIColumn(fEventsNtupleId, "nHitEnd");
  ana->FinishNtuple(fEventsNtupleId);

  // ---- EscapeNeutrons (one row per neutron that escapes satellite) ----
  fEscapesNtupleId = ana->CreateNtuple("EscapeNeutrons", "Neutrons crossing into WorldLV");
  ana->CreateNtupleIColumn(fEscapesNtupleId, "eventID");
  ana->CreateNtupleIColumn(fEscapesNtupleId, "trackID");
  ana->CreateNtupleIColumn(fEscapesNtupleId, "birthRegion");
  ana->CreateNtupleDColumn(fEscapesNtupleId, "birthE_MeV");
  ana->CreateNtupleDColumn(fEscapesNtupleId, "birthT_ns");
  ana->CreateNtupleIColumn(fEscapesNtupleId, "creatorCode");

  ana->CreateNtupleDColumn(fEscapesNtupleId, "escapeE_MeV");
  ana->CreateNtupleDColumn(fEscapesNtupleId, "escapeT_ns");
  ana->CreateNtupleDColumn(fEscapesNtupleId, "dirX");
  ana->CreateNtupleDColumn(fEscapesNtupleId, "dirY");
  ana->CreateNtupleDColumn(fEscapesNtupleId, "dirZ");
  ana->CreateNtupleDColumn(fEscapesNtupleId, "posX_mm");
  ana->CreateNtupleDColumn(fEscapesNtupleId, "posY_mm");
  ana->CreateNtupleDColumn(fEscapesNtupleId, "posZ_mm");

  // ---- Debug / human-readable helpers ----
  ana->CreateNtupleSColumn(fEscapesNtupleId, "creatorProcessName");
  ana->CreateNtupleSColumn(fEscapesNtupleId, "creatorCategory");
  ana->CreateNtupleIColumn(fEscapesNtupleId, "creatorProcessType");
  ana->CreateNtupleIColumn(fEscapesNtupleId, "creatorProcessSubType");
  ana->FinishNtuple(fEscapesNtupleId);

  // ---- PanelHits (one row per neutron entering a ScoringPanel) ----
  fPanelHitsNtupleId = ana->CreateNtuple("PanelHits", "Neutrons entering a ScoringPanel");
  ana->CreateNtupleIColumn(fPanelHitsNtupleId, "eventID");
  ana->CreateNtupleIColumn(fPanelHitsNtupleId, "trackID");
  ana->CreateNtupleIColumn(fPanelHitsNtupleId, "panel");
  ana->CreateNtupleDColumn(fPanelHitsNtupleId, "E_MeV");
  ana->CreateNtupleDColumn(fPanelHitsNtupleId, "t_ns");
  ana->CreateNtupleDColumn(fPanelHitsNtupleId, "posX_mm");
  ana->CreateNtupleDColumn(fPanelHitsNtupleId, "posY_mm");
  ana->CreateNtupleDColumn(fPanelHitsNtupleId, "posZ_mm");
  ana->CreateNtupleDColumn(fPanelHitsNtupleId, "dirX");
  ana->CreateNtupleDColumn(fPanelHitsNtupleId, "dirY");
  ana->CreateNtupleDColumn(fPanelHitsNtupleId, "dirZ");
  ana->CreateNtupleIColumn(fPanelHitsNtupleId, "birthRegion");
  ana->CreateNtupleDColumn(fPanelHitsNtupleId, "birthE_MeV");
  ana->CreateNtupleIColumn(fPanelHitsNtupleId, "creatorCode");
  ana->FinishNtuple(fPanelHitsNtupleId);
}


// PMRunAction.cc 
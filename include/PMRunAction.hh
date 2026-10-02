// PMRunAction.hh  (REPLACE WHOLE FILE)

#ifndef PMRUNACTION_HH
#define PMRUNACTION_HH

#include "G4UserRunAction.hh"
#include "G4Run.hh"

class PMRunAction : public G4UserRunAction {
public:
  explicit PMRunAction(const G4String& physName="");
  ~PMRunAction() override;

  void BeginOfRunAction(const G4Run*) override;
  void EndOfRunAction  (const G4Run*) override;

  int EventsId()  const { return fEventsNtupleId; }
  int EscapesId() const { return fEscapesNtupleId; }
  int RunConfigId() const { return fRunConfigNtupleId; }

  // -------- RunConfig ntuple columns (must match SetupOutput order) --------
  enum RunConfigCols {
    kCfg_runID = 0,
    kCfg_physicsListName,
    kCfg_snmMaterial,
    kCfg_sphereOuterR_mm,
    kCfg_sphereInnerR_mm,
    kCfg_beamParticle,
    kCfg_beamE_MeV,
    kCfg_beamDirX,
    kCfg_beamDirY,
    kCfg_beamDirZ,
    kCfg_pitchTable,
    kCfg_bDirX,
    kCfg_bDirY,
    kCfg_bDirZ
  };

  // -------- Events ntuple columns (must match SetupOutput order) --------
  enum EventsCols {
    kEvt_eventID = 0,
    kEvt_class,                 // 0=no hadronic vertex, 1=hadronic vertex, 2=SNM fission-like
    kEvt_vtxRegion,             // region code (0..5, or 99 unknown)
    kEvt_EpVtx_MeV,
    kEvt_t_vertex_ns,
    kEvt_nFissionsSNM,
    kEvt_t_firstFission_ns,

    kEvt_nBornTotal,
    kEvt_nBorn_r0,
    kEvt_nBorn_r1,
    kEvt_nBorn_r2,
    kEvt_nBorn_r3,
    kEvt_nBorn_r4,
    kEvt_nBorn_r5,

    kEvt_nEscapedTotal,
    kEvt_nEscBirth_r0,
    kEvt_nEscBirth_r1,
    kEvt_nEscBirth_r2,
    kEvt_nEscBirth_r3,
    kEvt_nEscBirth_r4,
    kEvt_nEscBirth_r5,

    // ---- Debug / human-readable helpers (keep at end to preserve existing indices) ----
    kEvt_hasPrimaryInelastic,   // 0/1
    kEvt_hasSNMFissionLike,     // 0/1
    kEvt_classLabel,            // string label for kEvt_class
    kEvt_vtxRegionName,         // string label for kEvt_vtxRegion
    kEvt_vtxProcName,           // name of process that defined the primary vertex step
    kEvt_vtxProcType,           // G4ProcessType (int)
    kEvt_vtxProcSubType,        // process subtype (int)
    kEvt_pitch_deg,             // primary pitch angle vs /pmgun/bDir (deg); -1 = fixed gun
    kEvt_hitBus,                // 0/1: primary proton entered the bus (region 1..5)
    kEvt_E_primary_MeV          // primary proton kinetic energy at generation
  };

  // -------- EscapeNeutrons ntuple columns --------
  enum EscapesCols {
    kEsc_eventID = 0,
    kEsc_trackID,
    kEsc_birthRegion,
    kEsc_birthE_MeV,
    kEsc_birthT_ns,
    kEsc_creatorCode,      // 0=Other/Unknown,1=RD,2=Deexcitation,3=Inelastic,4=Fission,5=Capture,6=Elastic

    kEsc_escapeE_MeV,
    kEsc_escapeT_ns,
    kEsc_dirX,
    kEsc_dirY,
    kEsc_dirZ,
    kEsc_posX,
    kEsc_posY,
    kEsc_posZ,

    // ---- Debug / human-readable helpers (keep at end to preserve existing indices) ----
    kEsc_creatorProcName,       // creator process name (e.g., "nFission", "protonInelastic")
    kEsc_creatorCategory,       // coarse label derived from creator process name
    kEsc_creatorType,           // G4ProcessType (int)
    kEsc_creatorSubType         // process subtype (int)
  };

private:
  void SetupOutput();

  G4String fPhysNameRequested;  // passed from action initialization

  int fRunConfigNtupleId = -1;
  int fEventsNtupleId{-1};
  int fEscapesNtupleId{-1};
};

#endif


// PMRUNACTION_HH

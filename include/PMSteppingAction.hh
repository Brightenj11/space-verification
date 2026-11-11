// PMSteppingAction.hh 

#ifndef PMSTEPPINGACTION_HH
#define PMSTEPPINGACTION_HH

#include "G4UserSteppingAction.hh"
#include "G4GenericMessenger.hh"
#include "G4ThreeVector.hh"
#include "G4VProcess.hh"
#include "G4String.hh"
#include <array>
#include <unordered_set>
#include <unordered_map>

class PMRunAction;
class G4Step;

class PMSteppingAction : public G4UserSteppingAction {
public:
  explicit PMSteppingAction(PMRunAction* runAction);
  ~PMSteppingAction() override;

  void UserSteppingAction(const G4Step* step) override;

  // Called by PMEventAction at EndOfEventAction to flush last event
  void EndOfEvent();

private:
  // Runtime toggles
  static G4double sMaxEventTime_ns;
  static G4bool   sKillGammas;
  static G4bool   sKillNeutronsAfterRecord; // debug-only (prevents escape tally)
  static G4bool   sKillNeutronsAfterEscape; // recommended true for your current vacuum world

  void BuildMessenger();
  void ResetEventStateIfNew(int evtId);
  void WriteEventsRow();

  // Region coding (your convention)
  static int RegionCodeFromLVName(const G4String& lvName);
  static int RegionCodeAtPoint(const G4StepPoint* p);

  // Human-readable region label (debug)
  static G4String RegionNameFromCode(int code);

  // Coarse creator code
  static int CreatorCode(const G4VProcess* proc); // 0=Other/Unknown,1=RD,2=Deexcitation,3=Inelastic,4=Fission,5=Capture,6=Elastic

  // Human-readable creator label (debug)
  static G4String CreatorCategory(const G4VProcess* proc);

  // Avoid commas/newlines in CSV string fields
  static G4String SanitizeForCSV(const G4String& s);

  // SNM-only fission-like latch/counting (heavy fragments in SNMSphereLV)
  void DetectSNMFissionLike(const G4Step* step, int preRegion);

  struct BirthInfo {
    int    region{99};
    double E_MeV{0.0};
    double t_ns{0.0};
    int    creator{0};

    // Debug-friendly creator details
    G4String creatorProcName{""};
    G4String creatorCategory{""};
    int      creatorType{-1};
    int      creatorSubType{-1};
  };

  PMRunAction*        fRunAction{nullptr};
  G4GenericMessenger* fMessenger{nullptr};

  // ---- per-thread, per-event state ----
  static thread_local int    t_evtId;

  static thread_local bool   t_seenPrimaryInelastic;
  static thread_local bool   t_primaryHitBus;
  static thread_local int    t_vtxRegion;
  static thread_local double t_EpVtx_MeV;
  static thread_local double t_tVtx_ns;

  // Process that defined the latched primary hadronic vertex step (debug)
  static thread_local G4String t_vtxProcName;
  static thread_local int      t_vtxProcType;
  static thread_local int      t_vtxProcSubType;

  static thread_local int    t_nFissionsSNM;
  static thread_local double t_tFirstFission_ns;

  static thread_local std::array<int,6> t_nBornByReg;
  static thread_local std::array<int,6> t_nEscByBirthReg;
  static thread_local std::array<int,2> t_nPanelHits;   // [0]=downstream panel, [1]=transverse panel

  static thread_local std::unordered_map<int, BirthInfo> t_birth;     // trackID -> birth info
  static thread_local std::unordered_set<int>            t_escaped;   // trackIDs already counted
};

#endif

// PMSteppingAction.hh 
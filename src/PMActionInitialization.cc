#include "PMActionInitialization.hh"
#include "PMRunAction.hh"
#include "PMSteppingAction.hh"
#include "PMPrimaryGenerator.hh"
#include "PMEventAction.hh"   // NEW

PMActionInitialization::PMActionInitialization(const G4String& physName)
: G4VUserActionInitialization(), fPhysName(physName)
{}

PMActionInitialization::~PMActionInitialization()
{}

void PMActionInitialization::BuildForMaster() const {
  SetUserAction(new PMRunAction(fPhysName));
}

void PMActionInitialization::Build() const {
  auto* runAct  = new PMRunAction(fPhysName);
  auto* stepAct = new PMSteppingAction(runAct);

  SetUserAction(runAct);
  SetUserAction(new PMPrimaryGenerator());
  SetUserAction(stepAct);
  SetUserAction(new PMEventAction(stepAct));   // NEW: flush per-event at EndOfEvent
}

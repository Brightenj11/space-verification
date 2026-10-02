#include "PMEventAction.hh"
#include "PMSteppingAction.hh"

PMEventAction::PMEventAction(PMSteppingAction* stepping)
: fStepping(stepping) {}

void PMEventAction::EndOfEventAction(const G4Event*) {
  if (fStepping) fStepping->EndOfEvent();
}

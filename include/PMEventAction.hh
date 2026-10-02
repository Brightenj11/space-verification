#ifndef PMEVENTACTION_HH
#define PMEVENTACTION_HH

#include "G4UserEventAction.hh"

class PMSteppingAction;

class PMEventAction : public G4UserEventAction {
public:
  explicit PMEventAction(PMSteppingAction* stepping);
  ~PMEventAction() override = default;

  void EndOfEventAction(const G4Event*) override;

private:
  PMSteppingAction* fStepping{nullptr};
};

#endif

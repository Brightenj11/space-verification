// PMPrimaryGenerator.hh
#ifndef PMPRIMARYGENERATOR_HH
#define PMPRIMARYGENERATOR_HH

#include "G4VUserPrimaryGeneratorAction.hh"
#include "G4String.hh"
#include "G4ThreeVector.hh"

class G4ParticleGun;
class G4Event;

class PMPrimaryGenerator : public G4VUserPrimaryGeneratorAction {
public:
  PMPrimaryGenerator();
  ~PMPrimaryGenerator() override;

  G4String GetParticleName() const;
  G4double GetEnergy() const;
  G4ThreeVector GetDirection() const;

  void GeneratePrimaries(G4Event* event) override;

private:
  G4ParticleGun* fGun; // one primary proton per event
};

#endif

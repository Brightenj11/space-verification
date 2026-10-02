// PMPrimaryGenerator.hh
#ifndef PMPRIMARYGENERATOR_HH
#define PMPRIMARYGENERATOR_HH

#include "G4VUserPrimaryGeneratorAction.hh"
#include "G4String.hh"
#include "G4ThreeVector.hh"
#include <vector>

class G4ParticleGun;
class G4Event;
class G4GenericMessenger;

class PMPrimaryGenerator : public G4VUserPrimaryGeneratorAction {
public:
  PMPrimaryGenerator();
  ~PMPrimaryGenerator() override;

  G4String GetParticleName() const;
  G4double GetEnergy() const;
  G4ThreeVector GetDirection() const;
  const G4String& GetPitchTable() const { return fPitchTablePath; }
  G4ThreeVector GetBDir() const { return fBDir.unit(); }
  G4double GetLastPitchDeg() const { return fLastPitchDeg; }

  void GeneratePrimaries(G4Event* event) override;

private:
  void LoadPitchTable();
  void BuildCdf();

  G4ParticleGun* fGun; // one primary proton per event
  G4GenericMessenger* fMessenger = nullptr;

  // AP9 pitch-angle mode (off while fPitchTablePath is empty): see /pmgun/ commands
  G4String fPitchTablePath;
  G4ThreeVector fBDir{0., 0., 1.};  // local B field direction in the bus frame. 0 0 1 runs along the bus axis

  G4String fLoadedPath;
  std::vector<G4double> fTableAngles;            // deg, ascending
  std::vector<G4double> fTableEnergies;          // MeV, ascending
  std::vector<std::vector<G4double>> fTableFlux; // [angle][energy]
  std::vector<G4double> fCdf;                    // over (pitch-angle bin, energy bin) cells
  G4double fLastPitchDeg = -1.;                  // pitch angle of the current event; -1 = fixed gun
};

#endif

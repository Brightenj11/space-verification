#include "PMPrimaryGenerator.hh"
#include "G4ParticleGun.hh"
#include "G4ParticleDefinition.hh"
#include "G4ParticleTable.hh"
#include "G4SystemOfUnits.hh"
#include "G4ThreeVector.hh"
#include "G4Event.hh"

PMPrimaryGenerator::PMPrimaryGenerator()
{
  fGun = new G4ParticleGun(1);
  auto* proton = G4ParticleTable::GetParticleTable()->FindParticle("proton");
  fGun->SetParticleDefinition(proton);

  // Simple test case: 100 MeV protons along +x toward origin (SNM at center).
  // Start inside world but outside the bus outer radius.
  fGun->SetParticleEnergy(100.*MeV);

  const G4double busOuterR = 750.0*mm;   // MUST match PMDetectorConstruction default fBusOuterRadius
  const G4double margin   = 100.0*mm;   // clearance outside hull
  fGun->SetParticlePosition(G4ThreeVector(-(busOuterR + margin), 0.0, 0.0));
  fGun->SetParticleMomentumDirection(G4ThreeVector(1.0, 0.0, 0.0)); // Travel along +x (from negative x toward origin)
  //const G4double startZ = -1100.0*mm; // Start 1.1 m from origin on -z axis (outside bus)
  //fGun->SetParticlePosition(G4ThreeVector(0.0, 0.0, startZ)); // Start outside the bus on the -z axis
  //fGun->SetParticleMomentumDirection(G4ThreeVector(0.0, 0.0, 1.0)); // Travel along +z (from negative z toward origin)
}

PMPrimaryGenerator::~PMPrimaryGenerator()
{
  delete fGun;
  fGun = nullptr;
}

G4String PMPrimaryGenerator::GetParticleName() const {
  return fGun->GetParticleDefinition()->GetParticleName();
}

G4double PMPrimaryGenerator::GetEnergy() const {
  return fGun->GetParticleEnergy();
}

G4ThreeVector PMPrimaryGenerator::GetDirection() const {
  return fGun->GetParticleMomentumDirection();
}

void PMPrimaryGenerator::GeneratePrimaries(G4Event* evt)
{
  fGun->GeneratePrimaryVertex(evt);
}

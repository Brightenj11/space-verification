#ifndef PMDETECTORCONSTRUCTION_HH
#define PMDETECTORCONSTRUCTION_HH

#include "G4VUserDetectorConstruction.hh"
#include "G4GenericMessenger.hh"
#include "G4LogicalVolume.hh"
#include "G4Material.hh"
#include "G4String.hh"

class G4VPhysicalVolume;

class PMDetectorConstruction : public G4VUserDetectorConstruction {
public:
  PMDetectorConstruction();
  ~PMDetectorConstruction() override;

  const G4String& GetSNMMaterialName() const { return fSNMMatName; }
  G4double GetBusOuterRadius() const { return fBusOuterRadius; }
  G4double GetBusLength() const { return fBusLength; }
  G4double GetSphereOuterRadius() const { return fSphereOuterRadius; }
  G4double GetSphereInnerRadius() const { return fSphereInnerRadius; }

  G4VPhysicalVolume* Construct() override;
  void ConstructSDandField() override;

private:
  // Methods to build special materials
  G4Material* BuildU235();
  G4Material* BuildHEU();
  G4Material* BuildPu239();
  G4Material* BuildWGPu();
  G4Material* BuildTi6Al4V();
  G4Material* BuildSS304L();
  G4Material* ResolveMaterial(const G4String& name);
  void BuildMessenger();

  // Messenger for runtime configuration
  G4GenericMessenger* fMessenger;

  // Geometry and material parameters (with default values)
  G4String fBusMatName;
  G4String fSNMMatName;
  G4double fBusOuterRadius;   // full outer radius of cylindrical bus (mm)
  G4double fBusWallThk;       // wall thickness of bus cylinder (mm)
  G4double fBusLength;        // full length (height) of bus cylinder (mm)
  G4double fBusEndcapThk;     // endcap thickness along Z (mm); set 0 for open-ended tube
  G4double fSphereOuterRadius; // outer radius of SNM sphere (mm)
  G4double fSphereInnerRadius; // inner radius of SNM sphere (mm) (for hollow sphere)

  // Logical volume pointers (for visualization or further use)
  G4LogicalVolume* fLogicBus;
  G4LogicalVolume* fLogicSNM;
  G4LogicalVolume* fLogicScoringPanel; // external vacuum scoring volume
};

#endif // PMDETECTORCONSTRUCTION_HH

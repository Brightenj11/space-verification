#include "PMDetectorConstruction.hh"

#include "G4NistManager.hh"
#include "G4Material.hh"
#include "G4Element.hh"
#include "G4Isotope.hh"
#include "G4Box.hh"
#include "G4Sphere.hh"
#include "G4Tubs.hh"
#include "G4LogicalVolume.hh"
#include "G4PVPlacement.hh"
#include "G4VisAttributes.hh"
#include "G4Colour.hh"
#include "G4SystemOfUnits.hh"
#include "G4ThreeVector.hh"
#include "G4GenericMessenger.hh"
#include "G4SubtractionSolid.hh"
#include <algorithm>


PMDetectorConstruction::PMDetectorConstruction()
: fMessenger(nullptr),
  // Set default materials and geometry sizes (estimated dimensions)
  fBusMatName("G4_Al"),      // default bus material: Aluminum
  fSNMMatName("WGPu"),       // default SNM material: WG Pu
  fBoxMatName("G4_Al"),      // default electronics payload material: Aluminum

  // --- BUS GEOMETRY ---
  fBusOuterRadius(750.0*mm), // bus outer radius (0.75 m)
  fBusWallThk(10.0*mm),      // bus wall thickness (1 cm)
  fBusEndcapThk(10.0*mm),    // endcap thickness (1 cm); set 0 for open tube


  // CHANGE THIS: make the bus 2 m long (as originally intended)
  fBusLength(2000.0*mm),     // full bus length (2 m)

  // --- SNM SPHERE GEOMETRY ---
  // CHANGE THESE: 30 cm outer radius, 20 cm inner radius
  fSphereOuterRadius(70.0*mm), // 7 cm outer radius
  fSphereInnerRadius(65.0*mm), // 6.5 cm inner radius (hollow sphere)

  // --- ELECTRONICS BOX GEOMETRY ---
  // CHANGE THESE: 50x50x60 cm (full dimensions)
  fBoxX(500.0*mm),           // 50 cm in X
  fBoxY(500.0*mm),           // 50 cm in Y
  fBoxZ(600.0*mm),           // 60 cm in Z

  fLogicBus(nullptr), fLogicSNM(nullptr), fLogicBox(nullptr), fLogicScoringPanel(nullptr)
{
  BuildMessenger();
}


PMDetectorConstruction::~PMDetectorConstruction() {
  delete fMessenger;
  fMessenger = nullptr;
}

void PMDetectorConstruction::BuildMessenger() {
  // Create a messenger for interactive configuration of the detector
  fMessenger = new G4GenericMessenger(this, "/det/", "Detector construction controls");

  // Material properties (allow selection via macro)
  fMessenger->DeclareProperty("busMaterial", fBusMatName)
    .SetGuidance("Material of the satellite bus (e.g. G4_Al, G4_Ti, G4_W, Ti6Al4V, SS304L)");
  fMessenger->DeclareProperty("snmMaterial", fSNMMatName)
    .SetGuidance("Material of the SNM payload (e.g. U235_solid for HEU, or other defined material)");
  fMessenger->DeclareProperty("boxMaterial", fBoxMatName)
    .SetGuidance("Material of the electronics payload box (e.g. G4_Al, SS304L)");

  // Geometric properties with units (can be adjusted via macro)
  fMessenger->DeclarePropertyWithUnit("busOuterRadius", "mm", fBusOuterRadius)
    .SetGuidance("Outer radius of cylindrical bus (in mm).");
  fMessenger->DeclarePropertyWithUnit("busWallThk", "mm", fBusWallThk)
    .SetGuidance("Wall thickness of bus cylinder (in mm).");
  fMessenger->DeclarePropertyWithUnit("busLength", "mm", fBusLength)
    .SetGuidance("Full length (height) of bus cylinder (in mm).");
  fMessenger->DeclarePropertyWithUnit("busEndcapThk", "mm", fBusEndcapThk)
  .SetGuidance("Endcap thickness along Z for the bus hull (mm). Set 0 for open-ended tube.");


  fMessenger->DeclarePropertyWithUnit("sphereOuterRadius", "mm", fSphereOuterRadius)
    .SetGuidance("Outer radius of SNM hollow sphere (in mm).");
  fMessenger->DeclarePropertyWithUnit("sphereInnerRadius", "mm", fSphereInnerRadius)
    .SetGuidance("Inner radius of SNM hollow sphere (in mm). Set 0 for a solid sphere.");
  
  fMessenger->DeclarePropertyWithUnit("boxSizeX", "mm", fBoxX)
    .SetGuidance("Full size of electronics payload box in X dimension (in mm).");
  fMessenger->DeclarePropertyWithUnit("boxSizeY", "mm", fBoxY)
    .SetGuidance("Full size of electronics payload box in Y dimension (in mm).");
  fMessenger->DeclarePropertyWithUnit("boxSizeZ", "mm", fBoxZ)
    .SetGuidance("Full size of electronics payload box in Z dimension (in mm).");
}

G4Material* PMDetectorConstruction::BuildU235() {
  if (auto* existing = G4Material::GetMaterial("U235_solid", false)) {
    return existing;
  }

  auto* isoU235 = new G4Isotope("U235", 92, 235, 235.04*g/mole);
  auto* elU235  = new G4Element("EnrichedUranium235", "U235", 1);
  elU235->AddIsotope(isoU235, 100.*perCent);

  auto* matU235 = new G4Material("U235_solid", 19.05*g/cm3, 1, kStateSolid);
  matU235->AddElement(elU235, 1);
  return matU235;
}

G4Material* PMDetectorConstruction::BuildHEU() {
  if (auto* existing = G4Material::GetMaterial("HEU", false)) {
    return existing;
  }

  // Define Isotopes
  auto* isoU235 = new G4Isotope("U235", 92, 235, 235.04*g/mole);
  auto* isoU238 = new G4Isotope("U238", 92, 238, 238.05*g/mole);

  // Define Element (Enriched Uranium)
  auto* elUEnriched = new G4Element("EnrichedUranium", "U_HEU", 2);
  elUEnriched->AddIsotope(isoU235, 90.0*perCent); // 90% Enrichment
  elUEnriched->AddIsotope(isoU238, 10.0*perCent); // 10% U-238

  // Define Material
  // Density of HEU is roughly 18.7 - 18.9 g/cm3 depending on casting.
  // We use 18.9 g/cm3 as a standard value for metal.
  auto* matHEU = new G4Material("HEU", 18.9*g/cm3, 1, kStateSolid);
  matHEU->AddElement(elUEnriched, 1);

  return matHEU;
}


G4Material* PMDetectorConstruction::BuildPu239() {
  // Check if already defined
  if (auto* existing = G4Material::GetMaterial("Pu239_solid", false)) {
    return existing;
  }

  // Define Isotope: Z=94, N=239, Atomic Mass ~239.05 g/mole
  auto* isoPu239 = new G4Isotope("Pu239", 94, 239, 239.05*g/mole);
  
  // Define Element from Isotope
  auto* elPu239  = new G4Element("Plutonium239", "Pu239", 1);
  elPu239->AddIsotope(isoPu239, 100.*perCent);

  // Define Material: Density ~19.8 g/cm3 (Alpha phase)
  auto* matPu239 = new G4Material("Pu239_solid", 19.8*g/cm3, 1, kStateSolid);
  matPu239->AddElement(elPu239, 1);
  
  return matPu239;
}

G4Material* PMDetectorConstruction::BuildWGPu() {
  // Check if already defined
  if (auto* existing = G4Material::GetMaterial("WGPu", false)) {
    return existing;
  }

  auto* nist = G4NistManager::Instance();

  // --- 1. Define Isotopes ---
  // Pu-239: ~239.05 g/mole
  auto* isoPu239 = new G4Isotope("Pu239", 94, 239, 239.052*g/mole);
  // Pu-240: ~240.05 g/mole (The high-neutron source)
  auto* isoPu240 = new G4Isotope("Pu240", 94, 240, 240.051*g/mole);

  // --- 2. Define Elements ---
  // Enriched Plutonium Element (Mix of 239 and 240)
  // Standard WGPu is roughly 94% Pu-239 and 6% Pu-240 by mass
  auto* elPuMixed = new G4Element("WeaponsGradePu", "Pu_WG", 2);
  elPuMixed->AddIsotope(isoPu239, 94.0*perCent);
  elPuMixed->AddIsotope(isoPu240,  6.0*perCent);

  // Gallium (Stabilizer for Delta Phase)
  // We can use natural Gallium from NIST
  auto* elGa = nist->FindOrBuildElement("Ga");

  // --- 3. Define Material ---
  // Density: ~15.8 g/cm3 (Delta Phase alloy density)
  // Composition: ~1 wt% Gallium, ~99 wt% Plutonium mixture
  auto* matWGPu = new G4Material("WGPu", 15.8*g/cm3, 2, kStateSolid);
  matWGPu->AddElement(elPuMixed, 99.0*perCent);
  matWGPu->AddElement(elGa,       1.0*perCent);

  return matWGPu;
}

G4Material* PMDetectorConstruction::ResolveMaterial(const G4String& name) {
  if (auto* existing = G4Material::GetMaterial(name, false)) return existing;

  if (name == "U235_solid") return BuildU235();
  if (name == "HEU")          return BuildHEU();
  if (name == "Pu239_solid")  return BuildPu239();
  if (name == "WGPu")         return BuildWGPu();

  auto* mat = G4NistManager::Instance()->FindOrBuildMaterial(name);
  if (!mat) {
    G4Exception("PMDetectorConstruction::ResolveMaterial", "BadMaterial", FatalException,
                ("Unknown material name: " + name).c_str());
  }
  return mat;
}


G4VPhysicalVolume* PMDetectorConstruction::Construct() {
  // Option to check for geometry overlaps
  const G4bool checkOverlaps = true;
  auto* nist = G4NistManager::Instance();

  // World Volume (vacuum environment)
  G4Material* vac = nist->FindOrBuildMaterial("G4_Galactic");
  G4double worldSize = 5000.0*mm; // half-size of world volume (5 m)
  G4Box* solidWorld = new G4Box("World", worldSize, worldSize, worldSize);
  G4LogicalVolume* logicWorld = new G4LogicalVolume(solidWorld, vac, "WorldLV");
  logicWorld->SetVisAttributes(G4VisAttributes::GetInvisible());
  G4VPhysicalVolume* physWorld = new G4PVPlacement(
      nullptr, G4ThreeVector(), logicWorld, "WorldPV", nullptr, false, 0, checkOverlaps);

  // Resolve materials for each component
  G4Material* busMat = ResolveMaterial(fBusMatName);
  G4Material* snmMat = ResolveMaterial(fSNMMatName);
  G4Material* boxMat = ResolveMaterial(fBoxMatName);

  // --- Bus envelope (vacuum interior + container for shell and internal payloads) ---
  const G4double busInnerR     = (fBusOuterRadius > fBusWallThk) ? (fBusOuterRadius - fBusWallThk) : 0.0;
  const G4double busHalfLength = 0.5 * fBusLength;
  

  // A solid cylinder volume filled with vacuum that defines "inside bus"
  auto* solidBusEnv = new G4Tubs("BusEnvelope", 0.0, fBusOuterRadius, busHalfLength, 0.*deg, 360.*deg);
  auto* logicBusEnv = new G4LogicalVolume(solidBusEnv, vac, "BusEnvelopeLV");
  new G4PVPlacement(nullptr, G4ThreeVector(0,0,0), logicBusEnv, "BusEnvelopePV",
                    logicWorld, false, 0, checkOverlaps);

  // --- Bus shell (hull) as daughter of envelope ---
  // Keep LV name "BusShellLV" so region=1 scoring remains valid for sidewall + endcaps.
    G4VSolid* solidBusShell = nullptr;

    if (fBusEndcapThk <= 0.0) {
      // Open-ended pipe (legacy behavior)
      solidBusShell = new G4Tubs("BusShell", busInnerR, fBusOuterRadius, busHalfLength, 0.*deg, 360.*deg);
    } else {
      // Closed cylinder: outer solid minus a shorter inner cavity
      const G4double capThk = std::min(fBusEndcapThk, busHalfLength);
      const G4double cavityHalfLength = busHalfLength - capThk; // interior length = L - 2*capThk

      if (cavityHalfLength <= 0.0) {
        G4Exception("PMDetectorConstruction::Construct", "BadGeometry", FatalException,
                    "busEndcapThk is too large for the requested busLength (interior cavity <= 0). "
                    "Require: busEndcapThk < busLength/2.");
      }

      auto* outerSolid  = new G4Tubs("BusOuterSolid", 0.0, fBusOuterRadius, busHalfLength, 0.*deg, 360.*deg);
      auto* innerCavity = new G4Tubs("BusInnerCavity", 0.0, busInnerR,      cavityHalfLength, 0.*deg, 360.*deg);

      solidBusShell = new G4SubtractionSolid("BusShell", outerSolid, innerCavity, nullptr, G4ThreeVector());
    }

    
    fLogicBus = new G4LogicalVolume(solidBusShell, busMat, "BusShellLV");
    new G4PVPlacement(nullptr, G4ThreeVector(0,0,0), fLogicBus, "BusShellPV",
                      logicBusEnv, false, 0, checkOverlaps);



  // --- SNM shell at origin, inside bus envelope ---
  auto* solidSNM = new G4Sphere("SNMSphere", fSphereInnerRadius, fSphereOuterRadius,
                                0.*deg, 360.*deg, 0.*deg, 180.*deg);
  fLogicSNM = new G4LogicalVolume(solidSNM, snmMat, "SNMSphereLV");
  new G4PVPlacement(nullptr, G4ThreeVector(0,0,0), fLogicSNM, "SNMSpherePV",
                    logicBusEnv, false, 0, checkOverlaps);

  // explicit SNM inner cavity volume so you can tag "inside SNM core" 
  if (fSphereInnerRadius > 0.0) {
    auto* solidSNMCore = new G4Sphere("SNMCore", 0.0, fSphereInnerRadius,
                                     0.*deg, 360.*deg, 0.*deg, 180.*deg);
    auto* logicSNMCore = new G4LogicalVolume(solidSNMCore, vac, "SNMCoreLV");
    new G4PVPlacement(nullptr, G4ThreeVector(0,0,0), logicSNMCore, "SNMCorePV",
                      logicBusEnv, false, 0, checkOverlaps);
  }

  // --- Electronics payload boxes as daughters of bus envelope ---
  const G4double halfX = 0.5 * fBoxX;
  const G4double halfY = 0.5 * fBoxY;
  const G4double halfZ = 0.5 * fBoxZ;

  auto* solidBox = new G4Box("ElectronicsBox", halfX, halfY, halfZ);
  fLogicBox = new G4LogicalVolume(solidBox, boxMat, "ElectronicsBoxLV");

  const G4double gap = 50.0*mm;
  const G4double placeZ = fSphereOuterRadius + halfZ + gap;

  new G4PVPlacement(nullptr, G4ThreeVector(0.0, 0.0,  placeZ), fLogicBox,
                    "ElectronicsBoxPV", logicBusEnv, false, 0, checkOverlaps);

  new G4PVPlacement(nullptr, G4ThreeVector(0.0, 0.0, -placeZ), fLogicBox,
                    "ElectronicsBoxPV_NegZ", logicBusEnv, false, 1, checkOverlaps);


  // --- External vacuum scoring panel (1 m^2 in YZ, 0.5 m thick in X) ---
  // Dimensions: Y=1.0 m, Z=1.0 m (area = 1 m^2), X=0.5 m (thickness)
  const G4double scoreHalfX = 0.25*m;
  const G4double scoreHalfY = 0.50*m;
  const G4double scoreHalfZ = 0.50*m;

  auto* solidScoringPanel = new G4Box("ScoringPanel", scoreHalfX, scoreHalfY, scoreHalfZ);
  fLogicScoringPanel = new G4LogicalVolume(solidScoringPanel, vac, "ScoringPanelLV");

  // Place ~1.75 m from origin in the +x,+z direction, centered on y=0 (straddles y-axis).
  // Using x=z=1.75/sqrt(2) m so that sqrt(x^2+z^2)=1.75 m.
  const G4double scoreX0 = 2000*mm;
  const G4double scoreZ0 = 1000*mm;

  new G4PVPlacement(nullptr, G4ThreeVector(scoreX0, 0.0, scoreZ0), fLogicScoringPanel,
                    "ScoringPanelPV", logicWorld, false, 0, checkOverlaps);


  // Visualization attributes for each component
  // Bus shell: semi-transparent (bluish gray)
  G4VisAttributes* visBus = new G4VisAttributes(G4Colour(0.5, 0.5, 0.8, 0.3)); // light blue-gray, semi-transparent
  visBus->SetForceSolid(true);
  fLogicBus->SetVisAttributes(visBus);
  // SNM sphere: semi-transparent red
  G4VisAttributes* visSNM = new G4VisAttributes(G4Colour(1.0, 0.0, 0.0, 0.4)); // red, semi-transparent
  visSNM->SetForceSolid(true);
  fLogicSNM->SetVisAttributes(visSNM);
  // Electronics box: semi-transparent green
  G4VisAttributes* visBox = new G4VisAttributes(G4Colour(0.5, 0.5, 0.8, 0.4)); // light blue-gray, semi-transparent
  visBox->SetForceSolid(true);
  fLogicBox->SetVisAttributes(visBox);

  // Scoring panel: orange (semi-transparent)
  G4VisAttributes* visScore = new G4VisAttributes(G4Colour(1.0, 0.55, 0.0, 0.35)); // orange
  visScore->SetForceSolid(true);
  fLogicScoringPanel->SetVisAttributes(visScore);

  return physWorld;
}

void PMDetectorConstruction::ConstructSDandField() {
  // No sensitive detectors or fields defined in this geometry
}

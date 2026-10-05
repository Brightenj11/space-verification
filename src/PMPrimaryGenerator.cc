#include "PMPrimaryGenerator.hh"
#include "G4ParticleGun.hh"
#include "G4ParticleDefinition.hh"
#include "G4ParticleTable.hh"
#include "G4SystemOfUnits.hh"
#include "G4ThreeVector.hh"
#include "G4Event.hh"
#include "G4GenericMessenger.hh"
#include "G4PhysicalConstants.hh"
#include "Randomize.hh"
#include "G4RunManager.hh"
#include "PMDetectorConstruction.hh"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <sstream>

namespace {
constexpr int kNAngleBins  = 360; // 0.5 deg pitch-angle bins over 0..180
constexpr int kNEnergyBins = 200; // log-spaced bins spanning the table's energy range

// Linear interpolation, clamped to the end values.
G4double Interp(const std::vector<G4double>& x, const std::vector<G4double>& y, G4double xi)
{
  if (xi <= x.front()) return y.front();
  if (xi >= x.back()) return y.back();
  const auto i = std::upper_bound(x.begin(), x.end(), xi) - x.begin();
  const G4double t = (xi - x[i-1]) / (x[i] - x[i-1]);
  return y[i-1] + t * (y[i] - y[i-1]);
}
}

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

  fMessenger = new G4GenericMessenger(this, "/pmgun/", "AP9 pitch-angle proton source");
  fMessenger->DeclareProperty("pitchTable", fPitchTablePath,
      "CSV from scripts/ap9_pitch_table.py; samples energy + direction from AP9 (empty = fixed gun)");
  fMessenger->DeclareProperty("bDir", fBDir, "Local magnetic field direction in the bus frame");
}

PMPrimaryGenerator::~PMPrimaryGenerator()
{
  delete fMessenger;
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

void PMPrimaryGenerator::LoadPitchTable()
{
  std::ifstream in(fPitchTablePath);
  if (!in) G4Exception("PMPrimaryGenerator", "PitchTable", FatalException,
                       ("cannot open " + fPitchTablePath).c_str());
  fTableAngles.clear(); fTableEnergies.clear(); fTableFlux.clear();
  std::string line;
  for (bool header = true; std::getline(in, line); header = false) {
    std::replace(line.begin(), line.end(), ',', ' ');
    std::istringstream ss(line);
    if (header) {
      std::string label; ss >> label;
      for (G4double e; ss >> e;) fTableEnergies.push_back(e);
      continue;
    }
    G4double angle;
    if (!(ss >> angle)) continue;
    std::vector<G4double> row;
    for (G4double v; ss >> v;) row.push_back(v);
    if (row.size() != fTableEnergies.size()) G4Exception("PMPrimaryGenerator", "PitchTable",
        FatalException, "pitch table row length does not match energy header");
    fTableAngles.push_back(angle);
    fTableFlux.push_back(row);
  }
  if (fTableAngles.empty()) G4Exception("PMPrimaryGenerator", "PitchTable", FatalException,
                                        "pitch table has no rows");
  fLoadedPath = fPitchTablePath;
  BuildCdf();
}

void PMPrimaryGenerator::BuildCdf()
{
  // Joint (pitch angle, energy) distribution: weight ~ j(E, alpha) * sin(alpha) * dE.
  // j is per steradian per MeV; dOmega = sin(alpha) dalpha dphi, and the gyrophase phi is uniform.
  const G4double logEmin = std::log(fTableEnergies.front());
  const G4double dLogE = (std::log(fTableEnergies.back()) - logEmin) / kNEnergyBins;

  // Flux at each fine-energy bin center, per tabulated angle. Log-log (power law) between table
  // energies, linear where an endpoint is zero (spectrum cut-off).
  std::vector<std::vector<G4double>> jFine(kNEnergyBins, std::vector<G4double>(fTableAngles.size()));
  for (int ie = 0; ie < kNEnergyBins; ++ie) {
    const G4double e = std::exp(logEmin + (ie + 0.5) * dLogE);
    const auto k = std::min<std::size_t>(
        std::upper_bound(fTableEnergies.begin(), fTableEnergies.end(), e) - fTableEnergies.begin(),
        fTableEnergies.size() - 1);
    const G4double e0 = fTableEnergies[k-1], e1 = fTableEnergies[k];
    for (std::size_t ia = 0; ia < fTableAngles.size(); ++ia) {
      const G4double j0 = fTableFlux[ia][k-1], j1 = fTableFlux[ia][k];
      jFine[ie][ia] = (j0 > 0. && j1 > 0.)
          ? j0 * std::pow(j1/j0, std::log(e/e0) / std::log(e1/e0))
          : j0 + (j1 - j0) * (e - e0) / (e1 - e0);
    }
  }

  // ponytail: linear in angle; a denser AP9 angle grid (5 deg) matters more than a fancier interpolant.
  // Trapped flux is symmetric about 90 deg; below the smallest tabulated angle it is the loss cone (0).
  fCdf.assign(kNAngleBins * kNEnergyBins + 1, 0.);
  for (int ia = 0; ia < kNAngleBins; ++ia) {
    const G4double alpha = (ia + 0.5) * 180. / kNAngleBins;
    const G4double folded = std::min(alpha, 180. - alpha);
    for (int ie = 0; ie < kNEnergyBins; ++ie) {
      const G4double dE = std::exp(logEmin + (ie + 1) * dLogE) - std::exp(logEmin + ie * dLogE);
      const G4double j = folded < fTableAngles.front() ? 0. : Interp(fTableAngles, jFine[ie], folded);
      const int cell = ia * kNEnergyBins + ie;
      fCdf[cell+1] = fCdf[cell] + j * std::sin(alpha*deg) * dE;
    }
  }
  if (fCdf.back() <= 0.) G4Exception("PMPrimaryGenerator", "PitchTable", FatalException,
                                     "pitch table has zero total flux");
  for (auto& c : fCdf) c /= fCdf.back();
}

void PMPrimaryGenerator::GeneratePrimaries(G4Event* evt)
{
  if (!fPitchTablePath.empty()) {
    if (fLoadedPath != fPitchTablePath) LoadPitchTable();

    // Draw one (angle, energy) cell; the proton gets the cell's center angle and energy.
    const auto cell = std::upper_bound(fCdf.begin(), fCdf.end(), G4UniformRand()) - fCdf.begin() - 1;
    const G4double alpha = (cell / kNEnergyBins + 0.5) * 180.*deg / kNAngleBins;
    const G4double logEmin = std::log(fTableEnergies.front());
    const G4double dLogE = (std::log(fTableEnergies.back()) - logEmin) / kNEnergyBins;
    fGun->SetParticleEnergy(std::exp(logEmin + (cell % kNEnergyBins + 0.5) * dLogE) * MeV);
    fLastPitchDeg = alpha/deg;
    const G4double gyro = twopi * G4UniformRand();
    const G4ThreeVector b = fBDir.unit();
    const G4ThreeVector e1 = b.orthogonal().unit(), e2 = b.cross(e1);
    const G4ThreeVector dir = std::cos(alpha)*b + std::sin(alpha)*(std::cos(gyro)*e1 + std::sin(gyro)*e2);

    // Uniform on a disk facing dir. Radius = bus bounding sphere (cylinder corner) + 50 mm margin,
    // so the disk covers the bus from any direction and, standing off by the same distance, starts outside it.
    const auto* det = static_cast<const PMDetectorConstruction*>(
        G4RunManager::GetRunManager()->GetUserDetectorConstruction());
    const G4double sourceR = std::hypot(det->GetBusOuterRadius(), 0.5*det->GetBusLength()) + 50.*mm;
    const G4ThreeVector u1 = dir.orthogonal().unit(), u2 = dir.cross(u1);
    const G4double r = sourceR * std::sqrt(G4UniformRand());
    const G4double psi = twopi * G4UniformRand();
    fGun->SetParticlePosition(-sourceR*dir + r*(std::cos(psi)*u1 + std::sin(psi)*u2));
    fGun->SetParticleMomentumDirection(dir);
  }
  fGun->GeneratePrimaryVertex(evt);
}

#include <iostream>
#include "G4RunManager.hh"
#include "G4MTRunManager.hh"
#include "G4ScoringManager.hh"
#include "G4TScoreHistFiller.hh"
#include "G4AnalysisManager.hh"
#include "G4UImanager.hh"
#include "G4VisManager.hh"
#include "G4VisExecutive.hh"
#include "G4UIExecutive.hh"
#include "G4EmParameters.hh"
#include "G4SystemOfUnits.hh" 
#include "G4PhysListFactory.hh"
#include "G4VModularPhysicsList.hh"
#include "G4RadioactiveDecayPhysics.hh"
#include "PMDetectorConstruction.hh"
#include "PMActionInitialization.hh"

 // Base Physics List
/* 
QGSP_BIC_HP  
QGSP_INCLXX_HP  **
FTFP_BERT_HP
FTFP_INCLXX_HP
*/

int main(int argc, char** argv)
{
    G4UIExecutive* ui = nullptr;

#ifdef G4MULTITHREADED
    auto* runManager = new G4MTRunManager;
#else
    auto* runManager = new G4RunManager;
#endif
    // Scoring commands
    G4ScoringManager* scoringManager = G4ScoringManager::GetScoringManager();
    G4ScoringManager::GetScoringManager();
    new G4TScoreHistFiller<G4AnalysisManager>;

    G4String plName = (argc >= 3) ? argv[2] : "FTFP_INCLXX_HP"; // or read getenv("PHYS")
    G4PhysListFactory factory;
    G4VModularPhysicsList* physicsList = factory.GetReferencePhysList(plName);
    if (!physicsList) { G4Exception("sim", "BadPhys", FatalException, ("Unknown PL: " + plName).c_str()); }

    // Optional: enable/disable radioactive decay with a third arg
    const bool useDecay = (argc >= 4) ? (G4String(argv[3]) == "decay") : false;
    if (useDecay) { physicsList->RegisterPhysics(new G4RadioactiveDecayPhysics()); }

    runManager->SetUserInitialization(physicsList);

    runManager->SetUserInitialization(new PMDetectorConstruction());
    runManager->SetUserInitialization(new PMActionInitialization(plName));

    if (argc == 1) {
        ui = new G4UIExecutive(argc, argv);
        G4VisManager* visManager = new G4VisExecutive();
        visManager->Initialize();
    }

    auto* UImanager = G4UImanager::GetUIpointer();

    if (ui) {
        UImanager->ApplyCommand("/control/execute vis.mac");
        ui->SessionStart();
        delete ui;
    } else {
        G4String command = "/control/execute ";
        G4String fileName = argv[1];
        UImanager->ApplyCommand(command + fileName);
    }

    return 0;
}

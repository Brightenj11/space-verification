#ifndef PMACTIONINITIALIZATION_HH
#define PMACTIONINITIALIZATION_HH


#include "G4VUserActionInitialization.hh"

#include "PMPrimaryGenerator.hh"
#include "PMRunAction.hh"

class PMActionInitialization : public G4VUserActionInitialization
{
public:
    explicit PMActionInitialization(const G4String& physName);
    ~PMActionInitialization();

    virtual void BuildForMaster() const;
    virtual void Build() const;

private:
    G4String fPhysName;
};

#endif
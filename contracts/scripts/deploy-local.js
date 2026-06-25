const hre = require("hardhat");
const fs = require('fs');

async function main() {
  console.log("=".repeat(60));
  console.log("Deploying SMART Framework to LOCAL Hardhat Network");
  console.log("=".repeat(60));
  console.log("");
  console.log("SMART Framework: Structured, Meaningful, Auditable, Responsible, and Transparent");
  console.log("");

  const [deployer, aiDeveloper, authenticator, publisher, admin] = await hre.ethers.getSigners();
  console.log("Deploying with account:", deployer.address);
  console.log("Account balance:", (await deployer.provider.getBalance(deployer.address)).toString());
  console.log("");

  console.log("Test Accounts:");
  console.log("  AI Developer:", aiDeveloper.address);
  console.log("  Authenticator:", authenticator.address);
  console.log("  Publisher:", publisher.address);
  console.log("  Admin:", admin.address);
  console.log("");

  // EIP-4337 canonical EntryPoint address
  const ENTRYPOINT_ADDRESS = "0x5FF137D4b0FDCD49DcA30c7CF57E578a026d2789";

  console.log("Phase 1: Deploying Core Infrastructure");
  console.log("-".repeat(60));

  console.log("1. Deploying SMARTIdentityRegistry (with claims)...");
  const SMARTIdentityRegistry = await hre.ethers.getContractFactory("SMARTIdentityRegistry");
  const identityRegistry = await SMARTIdentityRegistry.deploy();
  await identityRegistry.waitForDeployment();
  const identityRegistryAddress = await identityRegistry.getAddress();
  console.log("   SMARTIdentityRegistry:", identityRegistryAddress);

  console.log("2. Deploying SMARTUsernameRegistry...");
  const SMARTUsernameRegistry = await hre.ethers.getContractFactory("SMARTUsernameRegistry");
  const usernameRegistry = await SMARTUsernameRegistry.deploy();
  await usernameRegistry.waitForDeployment();
  const usernameRegistryAddress = await usernameRegistry.getAddress();
  console.log("   SMARTUsernameRegistry:", usernameRegistryAddress);

  console.log("");
  console.log("Phase 2: Deploying Account Abstraction (EIP-4337)");
  console.log("-".repeat(60));

  console.log("3. Deploying SMARTAccountFactory...");
  const SMARTAccountFactory = await hre.ethers.getContractFactory("SMARTAccountFactory");
  const accountFactory = await SMARTAccountFactory.deploy(usernameRegistryAddress);
  await accountFactory.waitForDeployment();
  const accountFactoryAddress = await accountFactory.getAddress();
  console.log("   SMARTAccountFactory:", accountFactoryAddress);

  console.log("4. Deploying SMARTPaymaster...");
  const SMARTPaymaster = await hre.ethers.getContractFactory("SMARTPaymaster");
  const paymaster = await SMARTPaymaster.deploy(ENTRYPOINT_ADDRESS);
  await paymaster.waitForDeployment();
  const paymasterAddress = await paymaster.getAddress();
  console.log("   SMARTPaymaster:", paymasterAddress);

  console.log("");
  console.log("Phase 3: Deploying Core Model Card Contracts");
  console.log("-".repeat(60));

  console.log("5. Deploying SMARTLifecycle (modular routing proxy + 6 modules)...");

  const RouterAdmin = await hre.ethers.getContractFactory("RouterAdmin");
  const routerAdmin = await RouterAdmin.deploy();
  await routerAdmin.waitForDeployment();
  const routerAdminAddress = await routerAdmin.getAddress();
  console.log("   RouterAdmin:           ", routerAdminAddress);

  const SMARTLifecycle = await hre.ethers.getContractFactory("SMARTLifecycle");
  const lifecycle = await SMARTLifecycle.deploy(deployer.address, routerAdminAddress);
  await lifecycle.waitForDeployment();
  const lifecycleAddress = await lifecycle.getAddress();
  console.log("   SMARTLifecycle proxy:  ", lifecycleAddress);

  const moduleSpecs = [
    { name: "RouterIntrospection" },
    { name: "LifecycleCore" },
    { name: "LifecycleQuorum" },
    { name: "LifecycleAdmin" },
    { name: "LifecycleNFT" },
    { name: "LifecycleLineage" },
  ];
  const moduleAddresses = {};
  const cuts = [];
  for (const spec of moduleSpecs) {
    const F = await hre.ethers.getContractFactory(spec.name);
    const c = await F.deploy();
    await c.waitForDeployment();
    const addr = await c.getAddress();
    moduleAddresses[spec.name] = addr;
    const selectors = [];
    for (const frag of F.interface.fragments) {
      if (frag.type === "function") selectors.push(frag.selector);
    }
    cuts.push({ moduleAddress: addr, action: 0, functionSelectors: selectors });
    console.log(`   ${spec.name.padEnd(22)}`, addr, `(${selectors.length} selectors)`);
  }

  const cutContract = await hre.ethers.getContractAt("RouterAdmin", lifecycleAddress);
  await (await cutContract.routerCut(cuts, hre.ethers.ZeroAddress, "0x")).wait();
  console.log("   routerCut applied (Add for all modules)");

  const adminFacet = await hre.ethers.getContractAt("LifecycleAdmin", lifecycleAddress);
  await (await adminFacet.initialize(deployer.address, "SMART Model Card", "SMART")).wait();
  console.log("   initialize() done");
  console.log("   SMARTLifecycle:", lifecycleAddress);

  console.log("6. Deploying SMARTRelayer...");
  const SMARTRelayer = await hre.ethers.getContractFactory("SMARTRelayer");
  const relayer = await SMARTRelayer.deploy(
    lifecycleAddress,
    accountFactoryAddress
  );
  await relayer.waitForDeployment();
  const relayerAddress = await relayer.getAddress();
  console.log("   SMARTRelayer:", relayerAddress);

  console.log("7. Deploying SMARTModelCardSBT (EIP-5192 + ERC-5484)...");
  const SMARTModelCardSBT = await hre.ethers.getContractFactory("SMARTModelCardSBT");
  const modelCardSBT = await SMARTModelCardSBT.deploy();
  await modelCardSBT.waitForDeployment();
  const modelCardSBTAddress = await modelCardSBT.getAddress();
  console.log("   SMARTModelCardSBT:", modelCardSBTAddress);

  console.log("8. Deploying ModelCardRegistry...");
  const ModelCardRegistry = await hre.ethers.getContractFactory("ModelCardRegistry");
  const modelCardRegistry = await ModelCardRegistry.deploy(identityRegistryAddress);
  await modelCardRegistry.waitForDeployment();
  const modelCardRegistryAddress = await modelCardRegistry.getAddress();
  console.log("   ModelCardRegistry:", modelCardRegistryAddress);

  console.log("9. Deploying SMARTNameRegistry...");
  const SMARTNameRegistry = await hre.ethers.getContractFactory("SMARTNameRegistry");
  const nameRegistry = await SMARTNameRegistry.deploy();
  await nameRegistry.waitForDeployment();
  const nameRegistryAddress = await nameRegistry.getAddress();
  console.log("   SMARTNameRegistry:", nameRegistryAddress);

  console.log("10. Deploying SMARTVersionRegistry...");
  const SMARTVersionRegistry = await hre.ethers.getContractFactory("SMARTVersionRegistry");
  const versionRegistry = await SMARTVersionRegistry.deploy();
  await versionRegistry.waitForDeployment();
  const versionRegistryAddress = await versionRegistry.getAddress();
  console.log("   SMARTVersionRegistry:", versionRegistryAddress);

  console.log("");
  console.log("Phase 4: Configuring Roles and Permissions");
  console.log("-".repeat(60));

  const DEVELOPER_ROLE = await adminFacet.DEVELOPER_ROLE();
  const AUTHENTICATOR_ROLE = await adminFacet.AUTHENTICATOR_ROLE();
  const PUBLISHER_ROLE = await adminFacet.PUBLISHER_ROLE();
  const ADMIN_ROLE = await adminFacet.ADMIN_ROLE();

  await (await adminFacet.grantRole(DEVELOPER_ROLE, relayerAddress)).wait();
  console.log("   Granted DEVELOPER_ROLE to SMARTRelayer");

  await (await adminFacet.grantRole(AUTHENTICATOR_ROLE, relayerAddress)).wait();
  console.log("   Granted AUTHENTICATOR_ROLE to SMARTRelayer");

  await (await adminFacet.grantRole(PUBLISHER_ROLE, relayerAddress)).wait();
  console.log("   Granted PUBLISHER_ROLE to SMARTRelayer");

  await (await adminFacet.grantRole(ADMIN_ROLE, deployer.address)).wait();
  console.log("   Granted ADMIN_ROLE to deployer");

  const HTA_ASSESSOR_ROLE = hre.ethers.id("HTA_ASSESSOR_ROLE");
  const htaAssessor = (await hre.ethers.getSigners())[5];
  await (await adminFacet.grantRole(HTA_ASSESSOR_ROLE, htaAssessor.address)).wait();
  console.log("   Granted HTA_ASSESSOR_ROLE to HTA assessor EOA:", htaAssessor.address);

  await accountFactory.setRelayer(relayerAddress);
  console.log("   Set relayer in SMARTAccountFactory");

  await usernameRegistry.transferOwnership(accountFactoryAddress);
  console.log("   Transferred SMARTUsernameRegistry ownership to SMARTAccountFactory");

  const ISSUER_MANAGER_ROLE = await identityRegistry.ISSUER_MANAGER_ROLE();
  await identityRegistry.grantRole(ISSUER_MANAGER_ROLE, deployer.address);
  console.log("   Granted ISSUER_MANAGER_ROLE to deployer in SMARTIdentityRegistry");

  await identityRegistry["addIssuer(address)"](deployer.address);
  console.log("   Added deployer as trusted issuer");

  await (await adminFacet.setIdentityRegistry(identityRegistryAddress)).wait();
  console.log("   Wired SMARTIdentityRegistry into SMARTLifecycle");

  const IDENTITY_ARBITER_ROLE = await adminFacet.IDENTITY_ARBITER_ROLE();
  await (await adminFacet.grantRole(IDENTITY_ARBITER_ROLE, deployer.address)).wait();
  console.log("   IDENTITY_ARBITER_ROLE granted to deployer");

  await (await adminFacet.setLineageRegistries(nameRegistryAddress, versionRegistryAddress)).wait();
  console.log("   Wired SMARTNameRegistry + SMARTVersionRegistry into SMARTLifecycle");

  const NAME_LIFECYCLE_ROLE = await nameRegistry.LIFECYCLE_ROLE();
  await nameRegistry.grantRole(NAME_LIFECYCLE_ROLE, lifecycleAddress);
  console.log("   Granted LIFECYCLE_ROLE on SMARTNameRegistry to SMARTLifecycle");

  const VERSION_LIFECYCLE_ROLE = await versionRegistry.LIFECYCLE_ROLE();
  await versionRegistry.grantRole(VERSION_LIFECYCLE_ROLE, lifecycleAddress);
  console.log("   Granted LIFECYCLE_ROLE on SMARTVersionRegistry to SMARTLifecycle");

  const VERSION_ARBITER_ROLE = await versionRegistry.VERSION_ARBITER_ROLE();
  console.log("   VERSION_ARBITER_ROLE configured (deployer is initial envelope arbiter)");

  console.log("");
  console.log("Configuring SBT-Lifecycle Integration");
  console.log("-".repeat(60));

  const MINTER_ROLE = await modelCardSBT.MINTER_ROLE();
  await modelCardSBT.grantRole(MINTER_ROLE, lifecycleAddress);
  console.log("   Granted MINTER_ROLE to SMARTLifecycle in SMARTModelCardSBT");

  await (await adminFacet.setSBTContract(modelCardSBTAddress)).wait();
  console.log("   Set SBT contract in SMARTLifecycle");

  const nftFacet = await hre.ethers.getContractAt("LifecycleNFT", lifecycleAddress);
  const sbtEnabled = await nftFacet.isSBTEnabled();
  console.log("   SBT integration enabled:", sbtEnabled);

  console.log("");
  console.log("Phase 5: Creating Test Accounts");
  console.log("-".repeat(60));

  // SMARTRole: Reader=0, AIDeveloper=1, Authenticator=2, Publisher=3, Admin=4
  const tx1 = await accountFactory.createAccount(aiDeveloper.address, "alice_dev", 1);
  await tx1.wait();
  const aliceAccount = await accountFactory.getAccount("alice_dev", 1);
  console.log("   Created AI Developer account for alice_dev:", aliceAccount);

  const tx2 = await accountFactory.createAccount(authenticator.address, "bob_auth", 2);
  await tx2.wait();
  const bobAccount = await accountFactory.getAccount("bob_auth", 2);
  console.log("   Created Authenticator account for bob_auth:", bobAccount);

  const tx3 = await accountFactory.createAccount(publisher.address, "carol_pub", 3);
  await tx3.wait();
  const carolAccount = await accountFactory.getAccount("carol_pub", 3);
  console.log("   Created Publisher account for carol_pub:", carolAccount);

  const tx4 = await accountFactory.createAccount(admin.address, "dave_admin", 4);
  await tx4.wait();
  const daveAccount = await accountFactory.getAccount("dave_admin", 4);
  console.log("   Created Admin account for dave_admin:", daveAccount);

  console.log("");
  console.log("Phase 5b: Seeding Identity Claims");
  console.log("-".repeat(60));

  // Claim type by transition: 1=ISSUER (developer), 2=AUTHENTICATOR, 3=PUBLISHER.
  async function seedClaim(identity, claimType, label) {
    const data = hre.ethers.toUtf8Bytes(label);
    const expiresAt = 0n;
    const messageHash = hre.ethers.solidityPackedKeccak256(
      ["address", "uint256", "bytes", "uint256"],
      [identity, claimType, data, expiresAt]
    );
    const signature = await deployer.signMessage(hre.ethers.getBytes(messageHash));
    const tx = await identityRegistry
      .connect(deployer)
      .addClaim(identity, claimType, data, "", expiresAt, signature);
    await tx.wait();
  }

  await seedClaim(aiDeveloper.address, 1, "alice_dev:AIDeveloper");
  console.log("   Seeded ISSUER claim for alice_dev EOA");

  await seedClaim(authenticator.address, 2, "bob_auth:Authenticator");
  console.log("   Seeded AUTHENTICATOR claim for bob_auth EOA");

  await seedClaim(publisher.address, 3, "carol_pub:Publisher");
  console.log("   Seeded PUBLISHER claim for carol_pub EOA");

  await seedClaim(admin.address, 1, "dave_admin:AdminAsIssuer");
  await seedClaim(admin.address, 3, "dave_admin:AdminAsPublisher");
  console.log("   Seeded ISSUER + PUBLISHER claims for dave_admin EOA");

  console.log("");
  console.log("   Skipping paymaster funding (EntryPoint not deployed on local network)");
  console.log("   In production, fund via: paymaster.deposit({value: 10 ETH})");

  console.log("");
  console.log("=".repeat(60));
  console.log("DEPLOYMENT COMPLETE");
  console.log("=".repeat(60));
  console.log("");
  console.log("SMART Framework Contract Addresses:");
  console.log("-".repeat(60));
  console.log("");
  console.log("Core Contracts:");
  console.log("  SMARTLifecycle:            ", lifecycleAddress);
  console.log("  SMARTRelayer:              ", relayerAddress);
  console.log("  SMARTIdentityRegistry:     ", identityRegistryAddress);
  console.log("  SMARTModelCardSBT:         ", modelCardSBTAddress);
  console.log("  ModelCardRegistry:         ", modelCardRegistryAddress);
  console.log("");
  console.log("Account Abstraction (EIP-4337):");
  console.log("  SMARTAccountFactory:       ", accountFactoryAddress);
  console.log("  SMARTPaymaster:            ", paymasterAddress);
  console.log("  SMARTUsernameRegistry:     ", usernameRegistryAddress);
  console.log("  EntryPoint:                ", ENTRYPOINT_ADDRESS);
  console.log("");
  console.log("Test Accounts (SMART Accounts):");
  console.log("  alice_dev (AI Developer):  ", aliceAccount);
  console.log("  bob_auth (Authenticator):  ", bobAccount);
  console.log("  carol_pub (Publisher):     ", carolAccount);
  console.log("  dave_admin (Admin):        ", daveAccount);
  console.log("");
  console.log("SMARTRole Enum Values:");
  console.log("  Reader: 0, AIDeveloper: 1, Authenticator: 2, Publisher: 3, Admin: 4");
  console.log("=".repeat(60));

  const deploymentInfo = {
    network: "localhost",
    chainId: 1337,
    deployer: deployer.address,
    timestamp: new Date().toISOString(),
    framework: "SMART",
    frameworkDescription: "Structured, Meaningful, Auditable, Responsible, and Transparent",
    eipStandards: {
      accountAbstraction: "EIP-4337",
      soulboundTokens: ["EIP-5192", "ERC-5484"],
      signatureValidation: ["EIP-712", "EIP-1271"],
      cloneFactory: "EIP-1167",
      deterministicDeploy: "CREATE2"
    },
    contracts: {
      core: {
        SMARTLifecycle: lifecycleAddress,
        SMARTRelayer: relayerAddress,
        SMARTIdentityRegistry: identityRegistryAddress,
        SMARTModelCardSBT: modelCardSBTAddress,
        ModelCardRegistry: modelCardRegistryAddress,
        SMARTNameRegistry: nameRegistryAddress,
        SMARTVersionRegistry: versionRegistryAddress,
      },
      lifecycleModules: {
        RouterAdmin: routerAdminAddress,
        ...moduleAddresses,
      },
      accountAbstraction: {
        SMARTAccountFactory: accountFactoryAddress,
        SMARTPaymaster: paymasterAddress,
        SMARTUsernameRegistry: usernameRegistryAddress,
        EntryPoint: ENTRYPOINT_ADDRESS,
      },
    },
    roles: {
      DEVELOPER_ROLE: DEVELOPER_ROLE,
      AUTHENTICATOR_ROLE: AUTHENTICATOR_ROLE,
      PUBLISHER_ROLE: PUBLISHER_ROLE,
      ADMIN_ROLE: ADMIN_ROLE,
      MINTER_ROLE: MINTER_ROLE,
    },
    integration: {
      sbtLifecycleIntegration: {
        enabled: true,
        lifecycleContract: lifecycleAddress,
        sbtContract: modelCardSBTAddress,
        description: "SMARTLifecycle automatically mints provenance SBTs on publish"
      }
    },
    smartRoles: {
      Reader: 0,
      AIDeveloper: 1,
      Authenticator: 2,
      Publisher: 3,
      Admin: 4,
    },
    testAccounts: {
      aiDeveloper: {
        username: "alice_dev",
        role: "AIDeveloper",
        roleIndex: 1,
        account: aliceAccount,
        signer: aiDeveloper.address,
      },
      authenticator: {
        username: "bob_auth",
        role: "Authenticator",
        roleIndex: 2,
        account: bobAccount,
        signer: authenticator.address,
      },
      publisher: {
        username: "carol_pub",
        role: "Publisher",
        roleIndex: 3,
        account: carolAccount,
        signer: publisher.address,
      },
      admin: {
        username: "dave_admin",
        role: "Admin",
        roleIndex: 4,
        account: daveAccount,
        signer: admin.address,
      },
    },
  };

  // /app and /deployments only exist inside the platform container; optional on host.
  try {
    fs.writeFileSync(
      "/app/deployments-localhost.json",
      JSON.stringify(deploymentInfo, null, 2)
    );
  } catch (err) {
    console.log("Could not write /app/deployments-localhost.json:", err.message);
  }

  try {
    fs.writeFileSync(
      "/deployments/addresses.json",
      JSON.stringify(deploymentInfo, null, 2)
    );
    console.log("\nDeployment info saved to /deployments/addresses.json");
  } catch (err) {
    console.log("\nCould not write to shared volume:", err.message);
  }

  const envContent = `# SMART Framework Contract Addresses
# Generated by deploy-local.js on ${new Date().toISOString()}
# SMART (Structured, Meaningful, Auditable, Responsible, and Transparent) Framework

# New SMART-prefixed variables (recommended)
SMART_ACCOUNT_FACTORY_ADDRESS=${accountFactoryAddress}
SMART_RELAYER_ADDRESS=${relayerAddress}
SMART_LIFECYCLE_ADDRESS=${lifecycleAddress}
SMART_LIFECYCLE_RELAYER_ADDRESS=${relayerAddress}
SMART_MODEL_CARD_SBT_ADDRESS=${modelCardSBTAddress}
SMART_IDENTITY_REGISTRY_ADDRESS=${identityRegistryAddress}
SMART_NAME_REGISTRY_ADDRESS=${nameRegistryAddress}
SMART_VERSION_REGISTRY_ADDRESS=${versionRegistryAddress}
SMART_USERNAME_REGISTRY_ADDRESS=${usernameRegistryAddress}
SMART_PAYMASTER_ADDRESS=${paymasterAddress}

# Legacy variable names (for backwards compatibility)
CONTRACT_ADDRESS=${accountFactoryAddress}
GASLESS_RELAYER_ADDRESS=${relayerAddress}
MLUCE_ADDRESS=${lifecycleAddress}
MLUCE_GASLESS_RELAYER_ADDRESS=${relayerAddress}
MODEL_CARD_SBT_ADDRESS=${modelCardSBTAddress}
IDENTITY_REGISTRY_ADDRESS=${identityRegistryAddress}
USERNAME_REGISTRY_ADDRESS=${usernameRegistryAddress}
MODEL_CARD_PAYMASTER_ADDRESS=${paymasterAddress}
MODEL_CARD_REGISTRY_ADDRESS=${modelCardRegistryAddress}

# EIP-4337 EntryPoint (canonical address)
ENTRYPOINT_ADDRESS=${ENTRYPOINT_ADDRESS}

# Chain configuration
CHAIN_ID=1337
INFURA_URL=http://hardhat:8545
`;

  try {
    fs.writeFileSync("/deployments/.env.contracts", envContent);
    console.log("Environment variables saved to /deployments/.env.contracts");
  } catch (err) {
    console.log("Could not write .env.contracts:", err.message);
  }

}

main()
  .then(() => {
    console.log("\nDeployment successful! Hardhat node will keep running...\n");
  })
  .catch((error) => {
    console.error("\nDeployment failed:", error);
    process.exit(1);
  });

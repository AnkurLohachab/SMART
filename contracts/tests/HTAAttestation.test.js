const { expect } = require("chai");
const hre = require("hardhat");

// Deploys the lifecycle diamond with all modules cut in, then initializes it.
// Mirrors deploy-local.js exactly: SMARTLifecycle(owner, routerAdmin), then
// routerCut for all six modules, then initialize().
async function deployLifecycle() {
  const [admin, dev, hta] = await hre.ethers.getSigners();

  const RouterAdmin = await hre.ethers.getContractFactory("RouterAdmin");
  const routerAdmin = await RouterAdmin.deploy();
  await routerAdmin.waitForDeployment();

  const Lifecycle = await hre.ethers.getContractFactory("SMARTLifecycle");
  const diamond = await Lifecycle.deploy(admin.address, await routerAdmin.getAddress());
  await diamond.waitForDeployment();
  const diamondAddr = await diamond.getAddress();

  // Use the RouterAdmin interface already wired into the diamond by the constructor
  const cut = await hre.ethers.getContractAt("RouterAdmin", diamondAddr);

  const modNames = [
    "RouterIntrospection",
    "LifecycleCore",
    "LifecycleQuorum",
    "LifecycleAdmin",
    "LifecycleNFT",
    "LifecycleLineage",
  ];
  const cuts = [];
  for (const name of modNames) {
    const F = await hre.ethers.getContractFactory(name);
    const m = await F.deploy();
    await m.waitForDeployment();
    const selectors = F.interface.fragments
      .filter(f => f.type === "function")
      .map(f => f.selector);
    cuts.push({ moduleAddress: await m.getAddress(), action: 0, functionSelectors: selectors });
  }
  await (await cut.routerCut(cuts, hre.ethers.ZeroAddress, "0x")).wait();

  // initialize() grants DEFAULT_ADMIN_ROLE + ADMIN_ROLE to admin
  const adminFacet = await hre.ethers.getContractAt("LifecycleAdmin", diamondAddr);
  await (await adminFacet.initialize(admin.address, "SMART Model Card", "SMART")).wait();

  return { diamond: diamondAddr, admin, dev, hta };
}

describe("attestHTA", function () {
  it("lets an HTA assessor attest a Published card and rejects non-assessors", async function () {
    const { diamond, admin, dev, hta } = await deployLifecycle();
    const core = await hre.ethers.getContractAt("LifecycleCore", diamond);
    const adminF = await hre.ethers.getContractAt("LifecycleAdmin", diamond);

    const HTA_ROLE = hre.ethers.id("HTA_ASSESSOR_ROLE");
    const DEV     = hre.ethers.id("DEVELOPER_ROLE");
    const AUTH    = hre.ethers.id("AUTHENTICATOR_ROLE");
    const PUB     = hre.ethers.id("PUBLISHER_ROLE");

    // admin already holds DEFAULT_ADMIN_ROLE + ADMIN_ROLE from initialize();
    // grant operational roles so admin can drive the card through the lifecycle.
    for (const r of [DEV, AUTH, PUB, HTA_ROLE]) {
      await (await adminF.grantRole(r, admin.address)).wait();
    }

    // Create → InEvaluation → Validated → Published
    const contentHash = hre.ethers.id("card-1");
    const tx = await core.createModelCard(admin.address, "ipfs://x", contentHash);
    await tx.wait();
    const tokenId = 1;

    await (await core.submitForEvaluation(tokenId, admin.address)).wait();
    await (await core.validateModelCard(tokenId, admin.address)).wait();
    await (await core.publishModelCard(tokenId, admin.address)).wait();

    // Happy path: admin holds HTA_ROLE and can attest a Published card
    const reportHash = hre.ethers.id("hta-report");
    await expect(core.attestHTA(tokenId, 0, reportHash))
      .to.emit(core, "HTAAttested");

    // Unhappy path: hta signer has no role → must revert
    await expect(core.connect(hta).attestHTA(tokenId, 0, reportHash)).to.be.reverted;
  });
});

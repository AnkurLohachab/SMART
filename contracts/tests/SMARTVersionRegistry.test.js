const { expect } = require("chai");
const hre = require("hardhat");

describe("SMARTVersionRegistry — lineage + envelope claims", function () {
  const RELATION = {
    Patch: 0,
    Recalibration: 1,
    Retrain: 2,
    Reformulation: 3,
    Reindication: 4,
    Withdrawal: 5,
  };
  const ENV_STATUS = {
    Asserted: 0,
    Disputed: 1,
    Upheld: 2,
    Repudiated: 3,
  };

  let registry, deployer, lifecycle, arbiter, alice, bob, mallory;
  const NAME_A = "copd-exacerbation-risk";
  const NAME_B = "uti-risk-predictor";
  const ENVELOPE_A = "0x" + "11".repeat(32);
  const ENVELOPE_B = "0x" + "22".repeat(32);

  function nameHash(name) {
    return hre.ethers.keccak256(hre.ethers.toUtf8Bytes(name));
  }

  beforeEach(async function () {
    [deployer, lifecycle, arbiter, alice, bob, mallory] = await hre.ethers.getSigners();
    const Registry = await hre.ethers.getContractFactory("SMARTVersionRegistry");
    registry = await Registry.deploy();
    await registry.waitForDeployment();

    await registry.grantRole(await registry.LIFECYCLE_ROLE(), lifecycle.address);
    await registry.grantRole(await registry.VERSION_ARBITER_ROLE(), arbiter.address);
  });

  // -------- pinning --------

  it("pins an envelope and records its provenance", async function () {
    const tx = await registry.connect(lifecycle).pinEnvelope(nameHash(NAME_A), ENVELOPE_A, alice.address);
    const r = await tx.wait();
    console.log(`        pinEnvelope gas:`, r.gasUsed.toString());

    const env = await registry.envelopeFor(nameHash(NAME_A));
    expect(env.hash).to.equal(ENVELOPE_A);
    expect(env.pinnedBy).to.equal(alice.address);
    expect(env.updatedAt).to.equal(0n);
  });

  it("rejects re-pin from a different controller", async function () {
    await registry.connect(lifecycle).pinEnvelope(nameHash(NAME_A), ENVELOPE_A, alice.address);
    await expect(
      registry.connect(lifecycle).pinEnvelope(nameHash(NAME_A), ENVELOPE_A, bob.address)
    ).to.be.revertedWith("Envelope pinned by different controller");
  });

  it("rejects re-pin with a different hash via pinEnvelope (must use updateEnvelope)", async function () {
    await registry.connect(lifecycle).pinEnvelope(nameHash(NAME_A), ENVELOPE_A, alice.address);
    await expect(
      registry.connect(lifecycle).pinEnvelope(nameHash(NAME_A), ENVELOPE_B, alice.address)
    ).to.be.revertedWith("Use updateEnvelope to change a pinned envelope");
  });

  it("updates an envelope hash without retroactively touching versions", async function () {
    await registry.connect(lifecycle).pinEnvelope(nameHash(NAME_A), ENVELOPE_A, alice.address);
    await registry.connect(lifecycle).mintVersion(
      1, nameHash(NAME_A), 0, RELATION.Patch, true, alice.address
    );

    await registry.connect(lifecycle).updateEnvelope(nameHash(NAME_A), ENVELOPE_B, alice.address);
    const env = await registry.envelopeFor(nameHash(NAME_A));
    expect(env.hash).to.equal(ENVELOPE_B);
    expect(env.updatedAt).to.be.gt(0n);

    // Existing version retains the old envelope hash
    const v1 = await registry.versionOf(1);
    expect(v1.envelopeHash).to.equal(ENVELOPE_A);
  });

  it("rejects updateEnvelope from a non-original pinner", async function () {
    await registry.connect(lifecycle).pinEnvelope(nameHash(NAME_A), ENVELOPE_A, alice.address);
    await expect(
      registry.connect(lifecycle).updateEnvelope(nameHash(NAME_A), ENVELOPE_B, bob.address)
    ).to.be.revertedWith("Only the original pinner may update");
  });

  // -------- minting --------

  it("mints a root version with supersedes==0 and Patch relation", async function () {
    await registry.connect(lifecycle).pinEnvelope(nameHash(NAME_A), ENVELOPE_A, alice.address);
    const tx = await registry.connect(lifecycle).mintVersion(
      1, nameHash(NAME_A), 0, RELATION.Patch, true, alice.address
    );
    const r = await tx.wait();
    console.log(`        mintVersion gas (root, withinEnvelope=true):`, r.gasUsed.toString());

    const v = await registry.versionOf(1);
    expect(v.tokenId).to.equal(1n);
    expect(v.supersedes).to.equal(0n);
    expect(v.relation).to.equal(RELATION.Patch);
    expect(v.envelopeHash).to.equal(ENVELOPE_A);
    expect(v.withinEnvelope).to.equal(true);
    expect(v.envelopeStatus).to.equal(ENV_STATUS.Asserted);

    expect(await registry.lineageLength(nameHash(NAME_A))).to.equal(1n);
  });

  it("mints a non-first version that supersedes the prior root", async function () {
    await registry.connect(lifecycle).pinEnvelope(nameHash(NAME_A), ENVELOPE_A, alice.address);
    await registry.connect(lifecycle).mintVersion(1, nameHash(NAME_A), 0, RELATION.Patch, true, alice.address);
    const tx = await registry.connect(lifecycle).mintVersion(
      2, nameHash(NAME_A), 1, RELATION.Recalibration, true, alice.address
    );
    const r = await tx.wait();
    console.log(`        mintVersion gas (successor):`, r.gasUsed.toString());

    const v2 = await registry.versionOf(2);
    expect(v2.supersedes).to.equal(1n);
    expect(v2.relation).to.equal(RELATION.Recalibration);

    const lineage = await registry.lineageOf(nameHash(NAME_A));
    expect(lineage.map(Number)).to.deep.equal([1, 2]);
  });

  it("rejects a first version with non-zero supersedes", async function () {
    await registry.connect(lifecycle).pinEnvelope(nameHash(NAME_A), ENVELOPE_A, alice.address);
    await expect(
      registry.connect(lifecycle).mintVersion(1, nameHash(NAME_A), 99, RELATION.Patch, false, alice.address)
    ).to.be.revertedWith("First version cannot supersede");
  });

  it("rejects a non-first version with supersedes==0", async function () {
    await registry.connect(lifecycle).mintVersion(1, nameHash(NAME_A), 0, RELATION.Patch, false, alice.address);
    await expect(
      registry.connect(lifecycle).mintVersion(2, nameHash(NAME_A), 0, RELATION.Retrain, false, alice.address)
    ).to.be.revertedWith("Non-first version must supersede");
  });

  it("rejects supersedes pointing to a different line", async function () {
    // NAME_A: tokenId 1 (root)
    await registry.connect(lifecycle).mintVersion(1, nameHash(NAME_A), 0, RELATION.Patch, false, alice.address);
    // NAME_B: tokenId 2 (root)
    await registry.connect(lifecycle).mintVersion(2, nameHash(NAME_B), 0, RELATION.Patch, false, alice.address);
    // NAME_B: tokenId 3 cannot supersede tokenId 1 (which is in NAME_A)
    await expect(
      registry.connect(lifecycle).mintVersion(3, nameHash(NAME_B), 1, RELATION.Retrain, false, alice.address)
    ).to.be.revertedWith("Predecessor not in this line");
  });

  it("rejects withinEnvelope=true when no envelope is pinned", async function () {
    await expect(
      registry.connect(lifecycle).mintVersion(1, nameHash(NAME_A), 0, RELATION.Patch, true, alice.address)
    ).to.be.revertedWith("Cannot claim withinEnvelope without a pinned envelope");
  });

  it("permits withinEnvelope=false on lines with no envelope", async function () {
    await registry.connect(lifecycle).mintVersion(1, nameHash(NAME_A), 0, RELATION.Patch, false, alice.address);
    const v = await registry.versionOf(1);
    expect(v.withinEnvelope).to.equal(false);
    expect(v.envelopeHash).to.equal("0x" + "00".repeat(32));
  });

  it("rejects a duplicate tokenId", async function () {
    await registry.connect(lifecycle).mintVersion(1, nameHash(NAME_A), 0, RELATION.Patch, false, alice.address);
    await expect(
      registry.connect(lifecycle).mintVersion(1, nameHash(NAME_A), 1, RELATION.Patch, false, alice.address)
    ).to.be.revertedWith("Version already recorded");
  });

  // -------- disputes --------

  it("challenges + resolves a withinEnvelope=true claim", async function () {
    await registry.connect(lifecycle).pinEnvelope(nameHash(NAME_A), ENVELOPE_A, alice.address);
    await registry.connect(lifecycle).mintVersion(1, nameHash(NAME_A), 0, RELATION.Patch, true, alice.address);

    const txC = await registry.connect(mallory).challengeEnvelope(1, "metrics outside declared bounds");
    const rC = await txC.wait();
    console.log(`        challengeEnvelope gas:`, rC.gasUsed.toString());
    let v = await registry.versionOf(1);
    expect(v.envelopeStatus).to.equal(ENV_STATUS.Disputed);
    expect(v.challenger).to.equal(mallory.address);

    const txR = await registry.connect(arbiter).resolveEnvelope(1, ENV_STATUS.Repudiated);
    const rR = await txR.wait();
    console.log(`        resolveEnvelope gas:`, rR.gasUsed.toString());
    v = await registry.versionOf(1);
    expect(v.envelopeStatus).to.equal(ENV_STATUS.Repudiated);
    expect(v.arbiter).to.equal(arbiter.address);
  });

  it("rejects challenge of a withinEnvelope=false version", async function () {
    await registry.connect(lifecycle).mintVersion(1, nameHash(NAME_A), 0, RELATION.Patch, false, alice.address);
    await expect(
      registry.connect(mallory).challengeEnvelope(1, "irrelevant")
    ).to.be.revertedWith("Cannot challenge a withinEnvelope=false claim");
  });

  it("rejects double-challenge", async function () {
    await registry.connect(lifecycle).pinEnvelope(nameHash(NAME_A), ENVELOPE_A, alice.address);
    await registry.connect(lifecycle).mintVersion(1, nameHash(NAME_A), 0, RELATION.Patch, true, alice.address);
    await registry.connect(mallory).challengeEnvelope(1, "first");
    await expect(
      registry.connect(bob).challengeEnvelope(1, "second")
    ).to.be.revertedWith("Already disputed or resolved");
  });

  it("enforces challenge window", async function () {
    await registry.connect(lifecycle).pinEnvelope(nameHash(NAME_A), ENVELOPE_A, alice.address);
    await registry.connect(lifecycle).mintVersion(1, nameHash(NAME_A), 0, RELATION.Patch, true, alice.address);

    // Fast-forward beyond default 90 days
    await hre.ethers.provider.send("evm_increaseTime", [91 * 24 * 60 * 60]);
    await hre.ethers.provider.send("evm_mine", []);

    await expect(
      registry.connect(mallory).challengeEnvelope(1, "too late")
    ).to.be.revertedWith("Challenge window closed");
  });

  it("only VERSION_ARBITER_ROLE can resolve", async function () {
    await registry.connect(lifecycle).pinEnvelope(nameHash(NAME_A), ENVELOPE_A, alice.address);
    await registry.connect(lifecycle).mintVersion(1, nameHash(NAME_A), 0, RELATION.Patch, true, alice.address);
    await registry.connect(mallory).challengeEnvelope(1, "claim invalid");
    await expect(
      registry.connect(mallory).resolveEnvelope(1, ENV_STATUS.Upheld)
    ).to.be.reverted;
  });

  it("rejects resolve to non-terminal status", async function () {
    await registry.connect(lifecycle).pinEnvelope(nameHash(NAME_A), ENVELOPE_A, alice.address);
    await registry.connect(lifecycle).mintVersion(1, nameHash(NAME_A), 0, RELATION.Patch, true, alice.address);
    await registry.connect(mallory).challengeEnvelope(1, "");
    await expect(
      registry.connect(arbiter).resolveEnvelope(1, ENV_STATUS.Disputed)
    ).to.be.revertedWith("Final status must be Upheld or Repudiated");
  });

  // -------- role gating --------

  it("only LIFECYCLE_ROLE can pin / mint / update", async function () {
    await expect(
      registry.connect(alice).pinEnvelope(nameHash(NAME_A), ENVELOPE_A, alice.address)
    ).to.be.reverted;
    await expect(
      registry.connect(alice).mintVersion(1, nameHash(NAME_A), 0, RELATION.Patch, false, alice.address)
    ).to.be.reverted;
    await expect(
      registry.connect(alice).updateEnvelope(nameHash(NAME_A), ENVELOPE_B, alice.address)
    ).to.be.reverted;
  });

  // -------- relation labels --------

  it("relationName resolves all six values", async function () {
    expect(await registry.relationName(RELATION.Patch)).to.equal("Patch");
    expect(await registry.relationName(RELATION.Recalibration)).to.equal("Recalibration");
    expect(await registry.relationName(RELATION.Retrain)).to.equal("Retrain");
    expect(await registry.relationName(RELATION.Reformulation)).to.equal("Reformulation");
    expect(await registry.relationName(RELATION.Reindication)).to.equal("Reindication");
    expect(await registry.relationName(RELATION.Withdrawal)).to.equal("Withdrawal");
  });
});

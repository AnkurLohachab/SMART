import { Address, createPublicClient, http } from "viem";
import { base } from "wagmi/chains";

// Minimal ABI fragments
export const modelCardSbtAbi = [
  {
    inputs: [{ internalType: "uint256", name: "", type: "uint256" }],
    name: "cardMeta",
    outputs: [
      { internalType: "bytes32", name: "cardHash", type: "bytes32" },
      { internalType: "string", name: "cid", type: "string" },
      { internalType: "string", name: "modelVersion", type: "string" },
      { internalType: "string", name: "runId", type: "string" },
      { internalType: "string", name: "schemaVersion", type: "string" },
      { internalType: "address", name: "issuer", type: "address" },
      { internalType: "uint64", name: "issuedAt", type: "uint64" },
      { internalType: "uint256", name: "supersedes", type: "uint256" },
    ],
    stateMutability: "view",
    type: "function",
  },
] as const;

export const publicClient = createPublicClient({
  chain: base,
  transport: http(),
});

export async function fetchCardMeta(contract: Address, tokenId: bigint) {
  const meta = await publicClient.readContract({
    address: contract,
    abi: modelCardSbtAbi,
    functionName: "cardMeta",
    args: [tokenId],
  });
  return meta;
}

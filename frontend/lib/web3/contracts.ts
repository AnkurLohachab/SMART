import { Address } from 'viem';
import { CONTRACT_ADDRESSES } from './config';

export const MODEL_CARD_REGISTRY_ABI = [
  {
    inputs: [
      { internalType: 'bytes32', name: 'modelIdHash', type: 'bytes32' },
      { internalType: 'address', name: 'sbtContract', type: 'address' },
      { internalType: 'uint256', name: 'tokenId', type: 'uint256' },
    ],
    name: 'register',
    outputs: [],
    stateMutability: 'nonpayable',
    type: 'function',
  },
] as const;

export const CUSTOM_ACCOUNT_FACTORY_ABI = [
  {
    inputs: [
      { internalType: 'string', name: 'username', type: 'string' },
      { internalType: 'uint8', name: 'role', type: 'uint8' },
    ],
    name: 'createAccount',
    outputs: [{ internalType: 'address', name: '', type: 'address' }],
    stateMutability: 'nonpayable',
    type: 'function',
  },
] as const;

export const GASLESS_RELAYER_ABI = [
  {
    inputs: [
      { internalType: 'string', name: 'username', type: 'string' },
      { internalType: 'uint8', name: 'role', type: 'uint8' },
      { internalType: 'bytes', name: 'signature', type: 'bytes' },
    ],
    name: 'relayAccountCreation',
    outputs: [{ internalType: 'address', name: '', type: 'address' }],
    stateMutability: 'nonpayable',
    type: 'function',
  },
] as const;

export const getContractConfig =(contractName: keyof typeof CONTRACT_ADDRESSES) => {
  const address = CONTRACT_ADDRESSES[contractName] as Address;

  switch (contractName) {
    case 'modelCardRegistry':
      return { address, abi: MODEL_CARD_REGISTRY_ABI };
    case 'customAccountFactory':
      return { address, abi: CUSTOM_ACCOUNT_FACTORY_ABI };
    case 'gaslessRelayer':
      return { address, abi: GASLESS_RELAYER_ABI };
    default:
      throw new Error(`Unknown contract: ${contractName}`);
  }
};

// Role enum matching Solidity.
export enum Role {
  Reader = 0,
  AIDeveloper = 1,
  Reviewer = 2,
  Admin = 3,
}

export const ROLE_NAMES = {
  [Role.Reader]: 'Reader',
  [Role.AIDeveloper]: 'AI Developer',
  [Role.Reviewer]: 'Reviewer',
  [Role.Admin]: 'Admin',
} as const;

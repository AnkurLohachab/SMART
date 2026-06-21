import { configureChains, createConfig } from 'wagmi';
import { hardhat, localhost, sepolia, polygon } from 'wagmi/chains';
import { publicProvider } from 'wagmi/providers/public';
import { getDefaultWallets } from '@rainbow-me/rainbowkit';

const { chains, publicClient, webSocketPublicClient } = configureChains(
  [
    hardhat,
    localhost,
    ...(process.env.NODE_ENV === 'production' ? [sepolia, polygon] : []),
  ],
  [publicProvider()]
);

const { connectors } = getDefaultWallets({
  appName: process.env.NEXT_PUBLIC_APP_NAME || 'SMART',
  projectId: process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID || '',
  chains,
});

export const wagmiConfig = createConfig({
  autoConnect: true,
  connectors,
  publicClient,
  webSocketPublicClient,
});

export { chains };

export const CONTRACT_ADDRESSES = {
  mluce: process.env.NEXT_PUBLIC_MLUCE_ADDRESS || '0xDc64a140Aa3E981100a9becA4E685f962f0cF6C9',
  modelCardSBT: process.env.NEXT_PUBLIC_MODEL_CARD_SBT_ADDRESS || '0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9',
  usernameRegistry: process.env.NEXT_PUBLIC_USERNAME_REGISTRY_ADDRESS || '0x5FbDB2315678afecb367f032d93F642f64180aa3',
  simpleAccountFactory: process.env.NEXT_PUBLIC_SIMPLE_ACCOUNT_FACTORY_ADDRESS || '0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512',
  simpleGaslessRelayer: process.env.NEXT_PUBLIC_SIMPLE_GASLESS_RELAYER_ADDRESS || '0x5FC8d32690cc91D4c39d9d3abcBD16989F875707',
} as const;

export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

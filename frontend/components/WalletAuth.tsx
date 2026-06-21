'use client';

import { ConnectButton } from '@rainbow-me/rainbowkit';
import { useAccount, useDisconnect } from 'wagmi';
import { useEffect } from 'react';

interface WalletAuthProps {
  onConnect?: (address: string) => void;
  onDisconnect?: () => void;
}

export function WalletAuth({ onConnect, onDisconnect }: WalletAuthProps) {
  const { address, isConnected } = useAccount();
  const { disconnect } = useDisconnect();

  useEffect(() => {
    if (isConnected && address && onConnect) {
      onConnect(address);
    }
  }, [isConnected, address, onConnect]);

  const handleDisconnect = () => {
    disconnect();
    if (onDisconnect) onDisconnect();
  };

  if (isConnected && address) {
    return (
      <div className="surface p-4 flex items-center justify-between gap-3">
        <div>
          <p className="meta">Wallet connected</p>
          <p className="mono text-[12.5px] mt-1">
            {address.slice(0, 6)}…{address.slice(-4)}
          </p>
        </div>
        <button onClick={handleDisconnect} className="btn btn-danger btn-sm">
          Disconnect
        </button>
      </div>
    );
  }

  return (
    <div className="surface p-4">
      <p className="meta mb-3">Optional: link a wallet to your account.</p>
      <ConnectButton.Custom>
        {({ account, chain, openConnectModal, mounted }) => {
          const ready = mounted;
          return (
            <div
              {...(!ready && {
                'aria-hidden': true,
                style: { opacity: 0, pointerEvents: 'none', userSelect: 'none' },
              })}
            >
              {(() => {
                if (!ready || !account || !chain) {
                  return (
                    <button
                      onClick={openConnectModal}
                      type="button"
                      className="btn btn-primary w-full"
                    >
                      Connect wallet
                    </button>
                  );
                }
                return null;
              })()}
            </div>
          );
        }}
      </ConnectButton.Custom>
    </div>
  );
}

import { useEffect, useState } from "react";
import { Address } from "viem";
import { fetchCardMeta } from "../lib/contracts";
import { sha256 } from "js-sha256";

type CardProps = {
  contract: Address;
  tokenId: bigint;
};

type ViewState = {
  loading: boolean;
  error?: string;
  verified?: boolean;
  cid?: string;
  cardJson?: any;
};

export function ModelCardViewer({ contract, tokenId }: CardProps) {
  const [state, setState] = useState<ViewState>({ loading: false });

  useEffect(() => {
    let mounted = true;
    async function load() {
      setState({ loading: true });
      try {
        const meta = await fetchCardMeta(contract, tokenId);
        const cid = meta[1] as string;
        const cardHashOnchain = meta[0] as string;
        const resp = await fetch(`https://ipfs.io/ipfs/${cid}`);
        if (!resp.ok) throw new Error("Failed to fetch IPFS content");
        const buf = await resp.arrayBuffer();
        const hashLocal = "0x" + sha256(new Uint8Array(buf));
        const verified = hashLocal.toLowerCase() === cardHashOnchain.toLowerCase();
        const text = new TextDecoder().decode(buf);
        const cardJson = JSON.parse(text);
        if (!mounted) return;
        setState({
          loading: false,
          verified,
          cid,
          cardJson,
        });
      } catch (err: any) {
        if (!mounted) return;
        setState({ loading: false, error: err?.message || "Error" });
      }
    }
    load();
    return () => {
      mounted = false;
    };
  }, [contract, tokenId]);

  if (state.loading) return <div className="card">Loading model card...</div>;
  if (state.error) return <div className="card">Error: {state.error}</div>;

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontWeight: 700 }}>Model Card</div>
          <div style={{ color: "#8aa4c4" }}>CID: {state.cid}</div>
        </div>
        <div
          style={{
            padding: "6px 10px",
            borderRadius: 8,
            background: state.verified ? "#16a34a33" : "#b91c1c33",
            color: state.verified ? "#4ade80" : "#f87171",
            fontWeight: 700,
          }}
        >
          {state.verified ? "Verified" : "Hash mismatch"}
        </div>
      </div>
      <pre style={{ marginTop: 12, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
        {JSON.stringify(state.cardJson, null, 2)}
      </pre>
    </div>
  );
}

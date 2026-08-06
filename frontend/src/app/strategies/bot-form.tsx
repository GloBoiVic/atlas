"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { isSupportedBotMode } from "@/lib/api";
import type { Bot, BotCreateRequest, BotMode, BotUpdateRequest, Strategy } from "@/lib/api";

interface BotFormProps {
  accountId: string;
  strategies: Strategy[];
  mode?: BotMode;
  bot?: Bot;
  busy: boolean;
  onCancel: () => void;
  onSubmit: (request: BotCreateRequest | BotUpdateRequest) => void;
}

function versions(strategies: Strategy[]): Strategy["versions"] {
  return strategies.flatMap((strategy) => strategy.versions);
}

export function BotForm({
  accountId,
  strategies,
  mode,
  bot,
  busy,
  onCancel,
  onSubmit,
}: BotFormProps): React.ReactElement {
  const availableVersions = versions(strategies);
  const existingMode = bot && isSupportedBotMode(bot.mode) ? bot.mode : undefined;
  const [name, setName] = useState(bot?.name ?? "");
  const [versionId, setVersionId] = useState(bot?.strategy_version_id ?? availableVersions[0]?.id ?? "");
  const [selectedMode, setSelectedMode] = useState<BotMode>(mode ?? existingMode ?? "paper");
  const [broker, setBroker] = useState(bot?.broker ?? "binance_usdm");
  const [instrument, setInstrument] = useState(bot?.instrument ?? "");
  const [timeframe, setTimeframe] = useState(bot?.timeframe ?? "1h");
  const [configText, setConfigText] = useState(JSON.stringify(bot?.config ?? {}, null, 2));
  const [error, setError] = useState<string | null>(null);

  if (bot && !existingMode) {
    return <section className="rounded-atlas-md border border-atlas-border bg-atlas-bg-elevated p-atlas-5" role="alert"><h2 className="text-atlas-lg font-atlas-semibold">Configuration unavailable</h2><p className="mt-atlas-2 text-atlas-sm text-atlas-warn">This bot has an unsupported execution mode. Paper/testnet controls are disabled until the API returns a supported mode.</p><Button className="mt-atlas-4" type="button" variant="outline" onClick={onCancel}>Close</Button></section>;
  }

  function submit(event: React.FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    try {
      const config = JSON.parse(configText) as unknown;
      if (typeof config !== "object" || config === null || Array.isArray(config)) {
        throw new Error("Configuration must be a JSON object.");
      }
      const common = {
        name: name.trim(),
        strategy_version_id: versionId,
        broker: broker.trim(),
        mode: selectedMode,
        instrument: instrument.trim(),
        timeframe: timeframe.trim(),
        config: config as Record<string, unknown>,
      };
      if (!common.name || !common.strategy_version_id || !common.instrument || !common.timeframe) {
        throw new Error("Name, strategy version, instrument, and timeframe are required.");
      }
      onSubmit(bot ? common : { ...common, account_id: accountId });
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Configuration is not valid JSON.");
    }
  }

  return (
    <form onSubmit={submit} className="rounded-atlas-md border border-atlas-border bg-atlas-surface p-atlas-5">
      <div className="flex items-start justify-between gap-atlas-4">
        <div>
          <h2 className="text-atlas-lg font-atlas-semibold">{bot ? "Edit bot configuration" : "Create bot"}</h2>
          <p className="mt-atlas-1 text-atlas-xs text-atlas-fg-secondary">Only paper and testnet modes are available. Strategy versions are immutable identities.</p>
        </div>
        <Button type="button" variant="ghost" onClick={onCancel}>Close</Button>
      </div>
      <div className="mt-atlas-5 grid gap-atlas-4 sm:grid-cols-2">
        <label className="text-atlas-sm">Name<input required value={name} onChange={(event) => setName(event.target.value)} className="mt-atlas-2 w-full rounded-atlas border border-atlas-border-strong bg-atlas-bg-elevated px-atlas-3 py-atlas-2 text-atlas-fg focus:ring-2 focus:ring-atlas-accent/30" /></label>
        <label className="text-atlas-sm">Strategy version<select required value={versionId} onChange={(event) => setVersionId(event.target.value)} className="mt-atlas-2 w-full rounded-atlas border border-atlas-border-strong bg-atlas-bg-elevated px-atlas-3 py-atlas-2 text-atlas-fg focus:ring-2 focus:ring-atlas-accent/30"><option value="">Select deployed version</option>{availableVersions.map((version) => <option key={version.id} value={version.id}>{version.id} · {version.commit_sha.slice(0, 8)}</option>)}</select></label>
         <label className="text-atlas-sm">Mode<select value={selectedMode} onChange={(event) => { if (isSupportedBotMode(event.target.value)) setSelectedMode(event.target.value); }} disabled={Boolean(bot)} className="mt-atlas-2 w-full rounded-atlas border border-atlas-border-strong bg-atlas-bg-elevated px-atlas-3 py-atlas-2 text-atlas-fg"><option value="paper">Paper</option><option value="testnet">Testnet</option></select></label>
        <label className="text-atlas-sm">Broker<input required value={broker} onChange={(event) => setBroker(event.target.value)} className="mt-atlas-2 w-full rounded-atlas border border-atlas-border-strong bg-atlas-bg-elevated px-atlas-3 py-atlas-2 text-atlas-fg" /></label>
        <label className="text-atlas-sm">Instrument<input required placeholder="BTCUSDT" value={instrument} onChange={(event) => setInstrument(event.target.value)} className="mt-atlas-2 w-full rounded-atlas border border-atlas-border-strong bg-atlas-bg-elevated px-atlas-3 py-atlas-2 text-atlas-fg" /></label>
        <label className="text-atlas-sm">Timeframe<input required value={timeframe} onChange={(event) => setTimeframe(event.target.value)} className="mt-atlas-2 w-full rounded-atlas border border-atlas-border-strong bg-atlas-bg-elevated px-atlas-3 py-atlas-2 text-atlas-fg" /></label>
      </div>
      <label className="mt-atlas-4 block text-atlas-sm">Strategy configuration <span className="text-atlas-fg-secondary">(JSON object)</span><textarea value={configText} onChange={(event) => setConfigText(event.target.value)} rows={5} className="mt-atlas-2 w-full rounded-atlas border border-atlas-border-strong bg-atlas-bg-elevated px-atlas-3 py-atlas-2 font-atlas-mono text-atlas-sm text-atlas-fg focus:ring-2 focus:ring-atlas-accent/30" /></label>
      {error ? <p className="mt-atlas-3 text-atlas-sm text-atlas-negative" role="alert">{error}</p> : null}
      <div className="mt-atlas-5 flex justify-end gap-atlas-3"><Button type="button" variant="outline" onClick={onCancel}>Cancel</Button><Button type="submit" disabled={busy || availableVersions.length === 0}>{busy ? "Saving…" : bot ? "Save configuration" : "Create stopped bot"}</Button></div>
    </form>
  );
}

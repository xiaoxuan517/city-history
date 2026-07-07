import { ChevronDown, RotateCcw } from "lucide-react";

import type { RetrievalProfile, SearchType } from "../types";

type RetrievalSettingsProps = {
  defaultProfile: RetrievalProfile | null;
  disabled: boolean;
  profile: RetrievalProfile | null;
  onChange: (profile: RetrievalProfile) => void;
};

const searchTypes: SearchType[] = ["similarity", "mmr", "hybrid"];

function RetrievalSettings({ defaultProfile, disabled, profile, onChange }: RetrievalSettingsProps) {
  if (!profile) {
    return (
      <details className="panel collapsible-panel">
        <summary className="panel-head">
          <h2>检索设置</h2>
          <ChevronDown size={16} aria-hidden="true" />
        </summary>
        <p className="panel-note">加载中</p>
      </details>
    );
  }

  function patchProfile(patch: Partial<RetrievalProfile>) {
    if (!profile) return;
    onChange(normalizeProfile({ ...profile, ...patch }));
  }

  return (
    <details className="panel collapsible-panel">
      <summary className="panel-head">
        <h2>检索设置</h2>
        <span className="collapse-actions">
          <button
            className="icon-button"
            disabled={disabled || !defaultProfile}
            onClick={(event) => {
              event.preventDefault();
              defaultProfile && onChange(defaultProfile);
            }}
            title="恢复默认检索设置"
            type="button"
          >
            <RotateCcw size={16} />
          </button>
          <ChevronDown size={16} aria-hidden="true" />
        </span>
      </summary>

      <div className="field-stack">
        <label className="field">
          <span>Search</span>
          <select
            value={profile.search_type}
            disabled={disabled}
            onChange={(event) => patchProfile({ search_type: event.target.value as SearchType })}
          >
            {searchTypes.map((searchType) => (
              <option key={searchType} value={searchType}>
                {searchType}
              </option>
            ))}
          </select>
        </label>

        <div className="field-grid">
          <NumberField
            disabled={disabled}
            label="Top K"
            min={1}
            value={profile.top_k}
            onChange={(value) => patchProfile({ top_k: value })}
          />
          <NumberField
            disabled={disabled}
            label="Fetch K"
            min={1}
            value={profile.fetch_k}
            onChange={(value) => patchProfile({ fetch_k: value })}
          />
        </div>

        <NumberField
          disabled={disabled}
          label="Context chars"
          min={1}
          value={profile.max_context_chars}
          onChange={(value) => patchProfile({ max_context_chars: value })}
        />

        <label className="toggle-field">
          <input
            type="checkbox"
            checked={profile.reranker_enabled}
            disabled={disabled}
            onChange={(event) => patchProfile({ reranker_enabled: event.target.checked })}
          />
          <span>Reranker</span>
        </label>

        <p className="panel-note">Fetch K 会自动保持不小于 Top K</p>
      </div>
    </details>
  );
}

function normalizeProfile(profile: RetrievalProfile): RetrievalProfile {
  const topK = Math.max(1, profile.top_k);
  return {
    ...profile,
    top_k: topK,
    fetch_k: Math.max(1, profile.fetch_k, topK),
    max_context_chars: Math.max(1, profile.max_context_chars),
  };
}

function NumberField({
  disabled,
  label,
  min,
  value,
  onChange,
}: {
  disabled: boolean;
  label: string;
  min: number;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        type="number"
        min={min}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(Math.max(min, Number(event.target.value) || min))}
      />
    </label>
  );
}

export default RetrievalSettings;

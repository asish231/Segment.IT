import React, { useEffect, useState } from 'react';
import { Copy, Check, Play, Loader2, Trash2, KeyRound } from 'lucide-react';
import { ApiKeySummary } from '../types';
import { createApiKey, listApiKeys, revokeApiKey, runSegmentApi } from '../services/api';

export const ApiPlaygroundScreen: React.FC = () => {
  const [keys, setKeys] = useState<ApiKeySummary[]>([]);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [keyName, setKeyName] = useState('default');
  const [loadingKeys, setLoadingKeys] = useState(true);
  const [copied, setCopied] = useState(false);

  const [running, setRunning] = useState(false);
  const [responseJson, setResponseJson] = useState<any>(null);
  const [responseError, setResponseError] = useState<string | null>(null);

  const loadKeys = () => {
    setLoadingKeys(true);
    listApiKeys().then(setKeys).catch(() => {}).finally(() => setLoadingKeys(false));
  };

  useEffect(loadKeys, []);

  const handleCreateKey = async () => {
    const result = await createApiKey(keyName || 'default');
    setNewKey(result.key);
    loadKeys();
  };

  const handleRevoke = async (id: string) => {
    await revokeApiKey(id);
    loadKeys();
  };

  const curlCommand = `curl -X POST http://127.0.0.1:8000/segment \\
  -H "Authorization: Bearer ${newKey || '<your API key>'}" \\
  -F "image=@page.png" \\
  -F "extract_tables=true" \\
  -F "ocr=true" \\
  -F "ocr_lang=en"`;

  const handleCopyCurl = () => {
    navigator.clipboard.writeText(curlCommand);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const handleRunSample = async () => {
    setRunning(true);
    setResponseError(null);
    try {
      const resp = await fetch('/samples/sample_test_subject_1.png');
      const blob = await resp.blob();
      const file = new File([blob], 'sample_test_subject_1.png', { type: blob.type });
      const result = await runSegmentApi(file, { extractTables: true, llmRefine: false });
      setResponseJson(result);
    } catch (err: any) {
      setResponseError(err.message || 'Request failed');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6 pb-14">
      <div className="border-b border-[#E8E2D9] pb-6">
        <h1 className="font-serif text-3xl text-[#2B2320] font-normal tracking-tight">API</h1>
        <p className="text-sm text-[#756C65] mt-1">Manage API keys and try the /segment endpoint.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <div className="bg-white border border-[#E8E2D9] rounded-2xl p-6 space-y-4">
            <h3 className="text-sm font-semibold text-[#2B2320]">API keys</h3>

            <div className="flex gap-2">
              <input
                value={keyName}
                onChange={(e) => setKeyName(e.target.value)}
                placeholder="Key name"
                className="flex-1 h-9 px-3 rounded-lg border border-[#E8E2D9] text-sm"
              />
              <button onClick={handleCreateKey} className="h-9 px-3 rounded-lg bg-[#2B2320] text-white text-xs font-semibold flex items-center gap-1.5">
                <KeyRound className="w-3.5 h-3.5" /> Create
              </button>
            </div>

            {newKey && (
              <div className="p-3 rounded-lg bg-[#FDF3E7] border border-[#F6E1C7] text-xs">
                <div className="font-semibold text-[#8A6318] mb-1">Copy this key now — it won't be shown again.</div>
                <code className="block break-all text-[#5A4415]">{newKey}</code>
              </div>
            )}

            {loadingKeys ? (
              <div className="text-xs text-[#A89F97] flex items-center gap-2"><Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading…</div>
            ) : keys.length === 0 ? (
              <p className="text-xs text-[#A89F97] italic">No API keys yet.</p>
            ) : (
              <div className="divide-y divide-[#F0ECE6]">
                {keys.map((k) => (
                  <div key={k.id} className="flex items-center justify-between py-2 text-xs">
                    <div>
                      <div className="font-semibold text-[#2B2320]">{k.name}</div>
                      <div className="text-[#A89F97]">{k.prefix}… · {new Date(k.created_at).toLocaleDateString()}</div>
                    </div>
                    {!k.revoked && (
                      <button onClick={() => handleRevoke(k.id)} className="text-[#A89F97] hover:text-[#E05A47]">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                    {k.revoked && <span className="text-[#A89F97]">revoked</span>}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-[#1E293B] text-[#93C5FD] rounded-2xl p-5 relative">
            <button onClick={handleCopyCurl} className="absolute top-3 right-3 p-1.5 rounded bg-white/10 hover:bg-white/20">
              {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
            <pre className="text-xs font-mono whitespace-pre-wrap leading-relaxed">{curlCommand}</pre>
          </div>
        </div>

        <div className="bg-white border border-[#E8E2D9] rounded-2xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-[#2B2320]">Try it</h3>
            <button
              onClick={handleRunSample}
              disabled={running}
              className="h-9 px-3 rounded-lg bg-[#2B2320] text-white text-xs font-semibold flex items-center gap-1.5 disabled:opacity-60"
            >
              {running ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
              Run on sample
            </button>
          </div>
          <div className="bg-[#0F172A] rounded-xl p-4 max-h-[500px] overflow-auto">
            {responseError ? (
              <p className="text-xs text-[#F87171]">{responseError}</p>
            ) : responseJson ? (
              <pre className="text-xs font-mono text-[#93C5FD] whitespace-pre-wrap">{JSON.stringify(responseJson, null, 2)}</pre>
            ) : (
              <p className="text-xs text-[#64748B]">Run a request to see the response.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

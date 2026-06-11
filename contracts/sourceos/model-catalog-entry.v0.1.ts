/**
 * SourceOS — Model/Adapter Catalog Entry Contract
 * Target: model-router (authority for routing + catalog resolution)
 *
 * Design basis:
 *  - Apple Foundation Models delivery (observed): frozen base + LoRA adapter overlays,
 *    content-addressed encrypted assets, pre-stage + atomic swap, cache-delete GC governor.
 *  - Anthropic Claude Code / OpenAI Codex (forensic, 2026-06-10): versioned bundle delivery
 *    done well, lifecycle GC done badly (version accumulation, orphan LaunchServices rows),
 *    capability surface gated by runtime prompt rather than declared + policy-admitted.
 *  - SourceOS differentiators: SAE interpretability, guardrail-fabric policy-as-code,
 *    Ontogenesis ontologies, SCOPE-D epistemic labeling, TriTRPC provenance wire,
 *    no-invisible-authority (everything declared, nothing discovered at runtime).
 *
 * Invariant: a model-router MUST refuse to admit or load an entry that fails
 * attestation, hash, capability-policy, or epistemic-label checks. Admission is the gate.
 */

// ── Enumerations ────────────────────────────────────────────────────────────

/** What kind of artifact this entry carries. Mirrors Apple's base/adapter split. */
export type ArtifactKind =
  | "base"          // full base model (the frozen general model)
  | "adapter"       // LoRA-style overlay bound to a specific base version
  | "steering"      // SAE steering vectors only (no weights)
  | "guardrail";    // policy/classifier artifact only

/** SAE steering capability tier (from Noetica: full | local | none, never boolean). */
export type SteeringTier = "full" | "local" | "none";

/** SCOPE-D epistemic level. An entry is inadmissible without one. */
export type EpistemicLevel =
  | "proved"
  | "bounded"
  | "empirical"
  | "synthetic"
  | "speculative"
  | "rejected"; // rejected entries are retained for audit but never loadable

/** Transport wire. TriTRPC is the SourceOS default (AEAD, byte-exact, ternary-native). */
export type CarryWire = "tritrpc" | "https-fallback";

// ── Sub-records ─────────────────────────────────────────────────────────────

/** Exact base-version binding. Forces adapter re-delivery on base change (Apple discipline). */
export interface BaseBinding {
  baseModelId: string;          // e.g. "sourceos.base.v3"
  baseVersion: string;          // exact semver; adapter is INVALID against any other
  baseContentHash: string;      // sha256 of the base this entry was trained/verified against
}

/** Content-addressed, encrypted artifact reference carried over the wire. */
export interface ArtifactRef {
  contentHash: string;          // sha256 — admission rejects on mismatch (hard stop)
  sizeBytes: number;
  encoding: "appleencryptedarchive-equiv" | "tritpack243" | "raw";
  encrypted: true;              // encryption-at-rest is an INVARIANT, not a flag to toggle
  wire: CarryWire;
}

/** Interpretability surface. Apple ships none of this; it is a SourceOS primitive. */
export interface InterpretabilitySurface {
  saeFeatureDictRef?: string;   // content hash of the SAE feature dictionary
  steeringVectors?: string[];   // content hashes of steering vectors (Neuronpedia-governed)
  steeringTier: SteeringTier;   // governs whether/how SAE steering may be applied
  // Hard rule carried from Noetica: when steering is applied, the steered-vs-baseline
  // diff MUST be surfaced. This flag asserts the entry supports diff emission.
  emitsSteeringDiff: boolean;
}

/** Governance bindings. Travel WITH the artifact, hash-bound — safety is part of identity. */
export interface GovernanceBinding {
  guardrailPolicyRef: string;   // policy-as-code admitted by guardrail-fabric
  ontologyRef?: string;         // Ontogenesis ontology for guided/constrained generation
}

/**
 * Declared capability surface (forensic lesson #2).
 * guardrail-fabric admits/denies on THIS, not on what a bundle registers at runtime.
 * Nothing may exercise a capability absent from declaredCapabilities.
 */
export interface CapabilityManifest {
  declaredCapabilities: string[];   // e.g. ["inference.text", "tool.read", "tool.computer-use"]
  requiredPermissions: string[];    // e.g. ["fs.read:/scoped", "net.egress:none"]
  highPrivilege: boolean;           // true ⇒ guardrail-fabric requires explicit policy grant
}

/**
 * Attestation (forensic lesson #3 — the codesign/TeamIdentifier analogue).
 * Checked at admission. Hash-chain anchors provenance across the TriTRPC boundary.
 */
export interface Attestation {
  signer: string;               // signing identity (the SourceOS analogue of TeamIdentifier)
  signature: string;            // detached signature over {contentHash, hashChain, capabilityManifest}
  hashChain: string[];          // ordered provenance hashes (assetId → content → policy → url)
  hardenedRuntime: boolean;     // mirrors the vendor hardened-runtime posture
}

/** Evaluation results. An entry without eval + epistemic label is inadmissible. */
export interface EvaluationRecord {
  evalFabricRunRef: string;     // content hash of the eval-fabric result set
  epistemicLevel: EpistemicLevel;
  evaluatedAt: string;          // RFC 3339
}

/**
 * Lifecycle (forensic lessons #1 and #4).
 * The entry OWNS its install/uninstall and retention. Do not leave GC to the OS registry —
 * that is exactly how Claude Code accumulated 15 versions and Codex left orphan LS rows.
 */
export interface Lifecycle {
  installManifest: {
    placements: string[];       // exact on-disk locations this entry writes
    registryRows: string[];     // exact registry/route rows it creates (for clean removal)
  };
  retentionPolicy: {
    keepVersions: number;       // e.g. 2 — reap older (Apple cache-delete discipline)
    reapOrphanRows: boolean;    // deregister + remove on uninstall; never accumulate
  };
}

// ── Top-level entry ─────────────────────────────────────────────────────────

export interface ModelCatalogEntry {
  // Identity
  id: string;                   // e.g. "sourceos.adapter.summarize"
  version: string;              // exact semver
  displayName: string;
  kind: ArtifactKind;

  // Carry
  baseBinding: BaseBinding;     // omit baseModelId only when kind === "base"
  artifact: ArtifactRef;

  // SourceOS-distinct surfaces (strictly more than Apple's {weights, adapter, hash})
  interpretability: InterpretabilitySurface;
  governance: GovernanceBinding;
  capability: CapabilityManifest;

  // Provenance + admission gates
  attestation: Attestation;
  evaluation: EvaluationRecord;

  // Operational
  lifecycle: Lifecycle;
  createdAt: string;            // RFC 3339
  sourceCommit?: string;        // originating repo commit, if applicable
}

// ── Admission ───────────────────────────────────────────────────────────────

export type AdmissionDenialReason =
  | "content_hash_mismatch"
  | "attestation_invalid"
  | "base_version_mismatch"
  | "capability_not_granted"
  | "missing_epistemic_label"
  | "epistemic_rejected"
  | "steering_diff_unsupported"; // entry claims steering but can't emit the diff

export interface AdmissionResult {
  admitted: boolean;
  entryId: string;
  denials: AdmissionDenialReason[];   // empty iff admitted
  evidenceRef?: string;               // agentplane provenance URI for the admission decision
}

/**
 * Reference admission contract. Implementation lives in model-router; guardrail-fabric
 * owns the capability/policy verdict. Every check here is a hard gate — a single failure
 * denies. The decision itself is emitted as provenance (no silent admission).
 */
export type AdmitEntry = (entry: ModelCatalogEntry) => Promise<AdmissionResult>;

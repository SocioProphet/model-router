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
 *  - ChatGPT client (forensic, 2026-06-10): egress fans out through a first-party /ces gateway
 *    to Statsig + Datadog before first frame, undeclared to the user; sentinel gates the send
 *    path via chat-requirements/{prepare,finalize} before model IO, silently.
 *  - SourceOS differentiators: SAE interpretability, guardrail-fabric policy-as-code,
 *    Ontogenesis ontologies, SCOPE-D epistemic labeling, TriTRPC provenance wire,
 *    no-invisible-authority (everything declared, nothing discovered at runtime).
 *
 * Invariant: a model-router MUST refuse to admit or load an entry that fails
 * attestation, hash, capability-policy, or epistemic-label checks. Admission is the gate.
 *
 * v0.1 → v0.2 additions:
 *  - EgressManifest with per-target permittedPhases (plugs the bootstrap-egress gap)
 *  - ObservabilitySurface with sinkInitializesBeforeIO and gatedBeforeIO (plugs silent-init gap)
 *  - ModelCatalogEntry.observability and .egress (both required)
 *  - AdmissionDenialReason: egress_target_not_permitted, observability_sink_uninitialized,
 *    cluster_not_admitted
 *  - AdmissionResult.clusterAdmissionRef: Triune admission-pack cross-reference
 *  - BaseBinding.baseModelId now optional for kind="base" entries (fixes TS validity)
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

/**
 * Execution phase during which a network target may be contacted.
 * Declaring permittedPhases per target prevents the bootstrap-egress pattern
 * (ChatGPT forensic: telemetry fires before the first user frame).
 */
export type ExecutionPhase = "bootstrap" | "inference" | "shutdown";

// ── Sub-records ─────────────────────────────────────────────────────────────

/**
 * Exact base-version binding. Forces adapter re-delivery on base change (Apple discipline).
 * baseModelId is optional for kind="base" entries (a base IS its own binding).
 */
export interface BaseBinding {
  baseModelId?: string;         // required for adapter/steering/guardrail; omit for base
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

/**
 * Egress manifest (forensic: ChatGPT client fans telemetry out through a first-party
 * /ces gateway to Statsig + Datadog, undeclared to the user).
 * SourceOS keeps the single-gateway pattern but every target is DECLARED here and
 * admitted by guardrail-fabric. No component may egress to a host not in this list.
 *
 * permittedPhases closes the bootstrap-egress gap: a target declared as
 * inference-only cannot contact the network during bootstrap or shutdown.
 */
export interface EgressManifest {
  targets: Array<{
    host: string;               // e.g. "evidence.sourceos.internal"
    purpose: "telemetry" | "provenance" | "experimentation" | "inference" | "feedback";
    processor: string;          // who actually receives it (first- or third-party), named
    wire: CarryWire;
    // Explicit phases this target may be contacted. Absent = no egress in that phase.
    // bootstrap egress requires explicit justification (audit trigger).
    permittedPhases: ExecutionPhase[];
  }>;
  // If false, the entry asserts it performs no network egress at all.
  permitsEgress: boolean;
}

/**
 * Observability surface (forensic: the entry.client bootstrap installs the telemetry
 * sink and reads feature flags BEFORE the first frame; sentinel gates the send path via
 * chat-requirements/{prepare,finalize} BEFORE model IO — both silently).
 * SourceOS mirrors the ordering but inverts the silence: the provenance sink and the
 * policy read MUST initialize before any inference is reachable, and every emission and
 * every gate verdict is surfaced rather than hidden.
 */
export interface ObservabilitySurface {
  provenanceSinkRef: string;    // agentplane evidence sink this entry emits to
  // What the entry emits as first-class, surfaced events (not silent instrumentation).
  emits: Array<"timing" | "error" | "feature_activation" | "steering_diff" | "gate_verdict">;
  // Bootstrap-ordering invariant (the entry.client lesson). Enforced at load:
  // the sink + policy read come up before model IO is reachable. No unobserved window.
  // Typed as literal true — false is structurally invalid and admission-denied.
  sinkInitializesBeforeIO: true;
  // Action-gate-before-IO (the sentinel/chat-requirements lesson). When true, a
  // guardrail-fabric admission must clear before inference — and its verdict is emitted.
  gatedBeforeIO: boolean;
}

// ── Top-level entry ─────────────────────────────────────────────────────────

export interface ModelCatalogEntry {
  // Identity
  id: string;                   // e.g. "sourceos.adapter.summarize"
  version: string;              // exact semver
  displayName: string;
  kind: ArtifactKind;

  // Carry
  baseBinding: BaseBinding;     // baseModelId optional for kind="base"; required otherwise
  artifact: ArtifactRef;

  // SourceOS-distinct surfaces (strictly more than Apple's {weights, adapter, hash})
  interpretability: InterpretabilitySurface;
  governance: GovernanceBinding;
  capability: CapabilityManifest;

  // Provenance + admission gates
  attestation: Attestation;
  evaluation: EvaluationRecord;

  // What it emits and where it may egress (declared, surfaced, policy-admitted)
  observability: ObservabilitySurface;
  egress: EgressManifest;

  // Cluster-level admission cross-reference.
  // When set, must be a non-empty Triune admission-pack reference (pack_id or URI).
  // An explicitly empty string triggers cluster_not_admitted denial.
  // Omit for synthetic/pre-cluster-admission entries.
  clusterAdmissionRef?: string;

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
  | "steering_diff_unsupported"    // entry claims steering but can't emit the diff
  | "egress_target_not_permitted"  // permitsEgress=true but a target lacks permittedPhases
  | "observability_sink_uninitialized" // sinkInitializesBeforeIO is not true
  | "cluster_not_admitted";        // clusterAdmissionRef is explicitly empty

export interface AdmissionResult {
  admitted: boolean;
  entryId: string;
  denials: AdmissionDenialReason[];   // empty iff admitted
  evidenceRef: string;                // always emitted — denied results get a denial URI
  // Triune cluster admission pack that admitted the node this entry runs on.
  // Present when the entry carries a clusterAdmissionRef and admission passed.
  clusterAdmissionRef?: string;
}

/**
 * Reference admission contract. Implementation lives in model-router; guardrail-fabric
 * owns the capability/policy verdict. Every check here is a hard gate — a single failure
 * denies. The decision itself is always emitted as provenance (no silent admission or
 * silent denial — AdmissionResult is written to the agentplane sink regardless of outcome).
 */
export type AdmitEntry = (entry: ModelCatalogEntry) => Promise<AdmissionResult>;

"""Adjudication of the 52 judge-vs-human disagreement cells in the Step-4 kappa run.

Verdict vocabulary (blind: decided from trace evidence vs the taxonomy operational
definition, THEN compared to who fired):

FP cells (judge fired, human majority NO):
  correct    - real failure present, humans missed it -> reclassify gold cell to POSITIVE (becomes TP)
  wrong      - judge fired on an absent failure OR mis-attributed the mode -> stays FP
  borderline - genuinely defensible either way / mode-overlap -> sensitivity (counted both ways)

FN cells (human fired, judge SILENT):
  miss       - real failure present, judge should have fired -> stays FN
  overlabel  - failure absent in trace-as-adapted, human over-labeled -> becomes TN (judge right)
  borderline - defensible / mode-overlap / version-confounded -> sensitivity

Each verdict carries a one-line evidence note. Verified = confirmed against literal trace text.
"""

# (trace, mode, fired_by_judge, human_yes, n_ann, verdict, evidence)
CELLS = [
    # ---- mad-1 HyperAgent v1 (277K) ----
    (1,  "FM-1.1", True,  0,3, "borderline", "Navigator fabricated contradictory impls; fabrication is closer to hallucination than task-spec disobey"),
    (1,  "FM-1.3", True,  0,3, "correct",    "Planner reissues identical subgoal s19/49/67; Navigator re-runs same open_file - real repetition, span-cited"),
    (1,  "FM-3.2", True,  0,3, "borderline", "Editor patch s135 empty Observation yet s136 declares success; conf 0.4, weak"),
    (1,  "FM-3.3", True,  0,3, "borderline", "'|' test errored s140 silently dropped, s141 claims success - plausible incorrect verification"),
    (1,  "FM-1.5", False, 3,3, "miss",       "Endless re-investigation loop = unaware of stopping; judge caught it under neighbor FM-1.3 (mode-overlap)"),
    # ---- mad-2 AG2 v1 (8.7K, fully read) ----
    (2,  "FM-1.3", True,  0,3, "borderline", "Identical 'Continue' x4 IS present but same failure humans tagged FM-1.5 (stopping); redundant double-label"),
    # ---- mad-3 ChatDev v1 (314K) ----
    (3,  "FM-1.1", True,  0,3, "correct",    "VERIFIED: task says 'sudoku solver/creator'; no generation code exists -> real spec violation humans missed"),
    (3,  "FM-1.2", False, 3,3, "borderline", "v1 18-mode label; ChatDev role-blur plausible but not individually verified in 314K trace (version-confounded)"),
    (3,  "FM-1.3", False, 3,3, "borderline", "ChatDev multi-phase repetition plausible; not verified (version-confounded)"),
    (3,  "FM-1.5", False, 3,3, "borderline", "not verified (version-confounded v1)"),
    (3,  "FM-2.1", False, 3,3, "overlabel",  "No conversation reset visible in ChatDev phase structure; likely v1 over-label"),
    (3,  "FM-2.3", False, 3,3, "borderline", "not verified (version-confounded v1)"),
    (3,  "FM-2.6", False, 3,3, "borderline", "not verified (version-confounded v1)"),
    # ---- mad-4 MetaGPT v1 (2.8K, fully read) ----
    (4,  "FM-1.5", False, 3,3, "borderline", "Run stops after 2 test rounds w/o convergence; plausible but terse log (data-limited)"),
    (4,  "FM-2.1", False, 3,3, "overlabel",  "No restart-from-scratch anywhere in trace; human over-label"),
    (4,  "FM-2.3", False, 3,3, "overlabel",  "Agents stay on palindrome task throughout; no derailment - human over-label"),
    (4,  "FM-2.6", False, 3,3, "borderline", "Reviewer content not in adapted trace (logs/21.txt external) - data-limited, cannot fairly decide"),
    (4,  "FM-3.3", False, 3,3, "borderline", "Reviewer/verification content external - data-limited"),
    # ---- mad-6 HyperAgent v2 (49K) ----
    (6,  "FM-1.1", True,  0,3, "correct",    "VERIFIED: trace contains 'pip uninstall scikit-learn' wiping the fix under test - real disobey humans missed"),
    (6,  "FM-1.3", True,  0,3, "correct",    "s11 restates s10 review verbatim - real repetition"),
    (6,  "FM-3.3", True,  0,3, "borderline", "verification-related; not deep-verified"),
    # ---- mad-7 AG2 v2 (7K, fully read) ----
    (7,  "FM-1.1", True,  0,3, "wrong",      "VERIFIED bug real (subtracts refused 10) BUT it is a reasoning error, not task-spec disobey; humans+judge caught it via FM-3.2/3.3. Mode mis-attribution"),
    # ---- mad-8 ChatDev v2 (314K) ----
    (8,  "FM-1.1", True,  0,3, "correct",    "VERIFIED: task requires 'check for mistakes'; check_solution never validates correctness - real spec gap"),
    (8,  "FM-3.2", True,  0,3, "correct",    "Test phase reports only 'run successfully' - verifies launch not Sudoku logic; real incomplete verification"),
    (8,  "FM-3.3", True,  0,3, "borderline", "reviewer said Finished then found flaw next cycle - defensible incorrect-verification, conf 0.4"),
    (8,  "FM-2.6", False, 3,3, "borderline", "ChatDev reasoning-action mismatch plausible; not individually verified in 314K"),
    # ---- mad-9 MetaGPT v2 (4.4K, fully read) ----
    (9,  "FM-2.2", True,  0,3, "borderline", "Negative-value ambiguity IS the same phenomenon humans tagged FM-2.6; defensible mode-overlap"),
    (9,  "FM-3.1", True,  0,3, "borderline", "Run ends w/ failing tests unresolved; MetaGPT fixed-round harness makes this weak"),
    (9,  "FM-3.2", True,  0,3, "correct",    "SimpleReviewer produces empty output both rounds; tests never executed - verification genuinely absent"),
    (9,  "FM-2.6", False, 3,3, "miss",       "Tester asserts negative-rejection the code never implements = reasoning/action mismatch; judge tagged it FM-2.2 instead (mode-overlap miss)"),
    # ---- mad-10 HyperAgent v2 (685K) ----
    (10, "FM-1.3", True,  1,3, "correct",    "Planner re-issues identical QDP subgoal s52/72/97/137...; 1 annotator agreed - real repetition"),
    (10, "FM-1.5", True,  0,3, "borderline", "endless loop, no def of done; overlaps FM-1.3"),
    (10, "FM-2.1", True,  0,3, "correct",    "Planner restarts from scratch with turn-1 framing after edits done - real conversation reset"),
    (10, "FM-2.6", True,  0,3, "correct",    "Editor claims function 'found' when not located, patches wrong function - reasoning-action mismatch"),
    (10, "FM-3.3", True,  0,3, "correct",    "VERIFIED: 'Table read successfully'+'1 passed' co-occur w/ unresolved ValueError - fabricated pass"),
    (10, "FM-1.1", False, 3,3, "miss",       "QDP-reader task spec violation humans unanimously saw; judge silent - genuine recall gap"),
    (10, "FM-2.2", False, 3,3, "miss",       "fail-to-clarify humans saw; judge under-fires FC2 clarification modes"),
    # ---- mad-12 AG2 v2 (12K) ----
    (12, "FM-2.2", False, 3,3, "miss",       "Chalk problem has distraction insertion (0.5oz red herring); fail-to-detect-ambiguity real, judge missed"),
    (12, "FM-2.3", False, 3,3, "borderline", "derailment on distraction plausible; judge caught FM-1.1/3.2 instead"),
    # ---- mad-13 ChatDev v2 (324K) ----
    (13, "FM-1.1", True,  0,3, "correct",    "VERIFIED: task requires clues; GUI renders none - real spec gap humans missed"),
    (13, "FM-3.2", True,  0,3, "correct",    "reviewers never check grid-fit/intersection consistency - incomplete verification"),
    (13, "FM-2.2", False, 2,3, "borderline", "2/3 split; not verified"),
    # ---- mad-14 MetaGPT v2 (2.6K, fully read) ----
    (14, "FM-1.3", True,  0,3, "correct",    "VERIFIED: SimpleTester re-emits s2 test suite in s4 changing one assertion - real repetition"),
    (14, "FM-3.1", True,  0,3, "borderline", "ends w/ buggy code (fib(0)) tests unrun; MetaGPT fixed-round harness weakens 'premature'"),
    (14, "FM-3.2", True,  0,3, "correct",    "VERIFIED: SimpleReviewer INFO-only both rounds, tests never executed - verification absent"),
    (14, "FM-2.2", False, 2,3, "borderline", "2/3 split; negative-limit ambiguity plausible"),
    # ---- mad-15 ChatDev final (316K) ----
    (15, "FM-1.3", True,  0,3, "correct",    "Programmer re-emits byte-identical code across 3 cycles after 'Finished' - real repetition"),
    (15, "FM-2.3", True,  0,3, "correct",    "VERIFIED: MCQ task reframed as GUI quiz app via DemandAnalysis - textbook derailment humans missed"),
    (15, "FM-3.2", False, 2,3, "borderline", "2/3 split incomplete-verification; judge caught FM-3.3 instead (overlap)"),
    # ---- mad-16 MetaGPT final (6.7K, fully read) ----
    (16, "FM-2.3", True,  0,3, "correct",    "VERIFIED: tester/reviewer loop on Java compareTo Unicode tangent, never finalize MCQ answer - derailment"),
    (16, "FM-3.1", True,  0,3, "correct",    "VERIFIED: ends on reviewer critique, wrong answer(0) never corrected - incomplete/premature"),
    (16, "FM-1.1", False, 2,3, "miss",       "MCQ output format disobeyed (built GUI); judge caught via FM-2.3 derailment (mode-overlap)"),
]

# --- Second-opinion pass (adversarial): the 10 FP `borderline` cells re-judged
# from fresh trace evidence, trying to prove the judge WRONG. Resolves each to a
# firm correct/wrong so precision stops being a band. 4 correct, 6 wrong. ---
SECOND_OPINION = {
    (1,  "FM-1.1"): "wrong",    # contradictory impls real but invented-content, not spec-disobey (mode stretch)
    (1,  "FM-3.2"): "correct",  # 'issue has been resolved' declared on an unexecuted patch
    (1,  "FM-3.3"): "correct",  # success claimed on predicted 'output will be the same', never run
    (2,  "FM-1.3"): "wrong",    # redundant 2nd label of the loop humans tagged once as FM-1.5
    (6,  "FM-3.3"): "correct",  # 'Pipeline fitted successfully' fabricated, never run; Planner accepts
    (8,  "FM-3.3"): "correct",  # reviewer 'Finished' then found real flaw next cycle
    (9,  "FM-2.2"): "wrong",    # fixed pipeline, no clarify opportunity; humans' FM-2.6 is sharper
    (9,  "FM-3.1"): "wrong",    # MetaGPT ends structurally, not a premature-termination decision
    (10, "FM-1.5"): "wrong",    # redundant with corroborated FM-1.3/2.1 loop firings
    (14, "FM-3.1"): "wrong",    # same structural-end mislabel as mad-9
}
CELLS = [(t,m,j,h,n,SECOND_OPINION.get((t,m),v),e) for (t,m,j,h,n,v,e) in CELLS]

from collections import Counter
fp = [c for c in CELLS if c[2]]
fn = [c for c in CELLS if not c[2]]
print("=== FP verdicts (judge fired, human no) ===")
print(Counter(c[5] for c in fp))
print("=== FN verdicts (human fired, judge silent) ===")
print(Counter(c[5] for c in fn))

# Baseline agreement cells (unchanged), PINNED to evals/kappa_report.json's `overall`
# block for the current judge run. Re-derive these if the judge is ever re-run.
TP0, FP0, FN0, TN0 = 20, 30, 22, 112

def recompute(borderline_fp_as_tp, borderline_fn_as_fn):
    tp, fp_, fn_, tn = TP0, 0, 0, TN0
    # start from agreements: TP0 true-agree-yes, TN0 true-agree-no
    for (_,_,j,_,_,v,_) in fp:  # judge yes, human no
        if v == "correct":      tp += 1            # gold was wrong-neg -> now agree-yes
        elif v == "wrong":      fp_ += 1           # stays FP
        elif v == "borderline": (tp := tp+1) if borderline_fp_as_tp else (fp_ := fp_+1)
    for (_,_,j,_,_,v,_) in fn:  # judge no, human yes
        if v == "miss":         fn_ += 1           # stays FN
        elif v == "overlabel":  tn += 1            # gold was wrong-pos -> now agree-no
        elif v == "borderline": (fn_ := fn_+1) if borderline_fn_as_fn else (tn := tn+1)
    prec = tp/(tp+fp_) if tp+fp_ else None
    rec  = tp/(tp+fn_) if tp+fn_ else None
    # Cohen kappa on 2x2
    n = tp+fp_+fn_+tn
    po = (tp+tn)/n
    p_yes = ((tp+fp_)/n)*((tp+fn_)/n)
    p_no  = ((fn_+tn)/n)*((fp_+tn)/n)
    pe = p_yes+p_no
    kappa = (po-pe)/(1-pe)
    return dict(tp=tp,fp=fp_,fn=fn_,tn=tn,precision=round(prec,3),recall=round(rec,3),kappa=round(kappa,3))

print("\n=== ADJUDICATED metrics (agreements assumed correct; 52 disagreements re-judged) ===")
print("Naive (as-scored):        precision=0.40 recall=0.476 kappa=0.248")
print("Adjudicated, borderline CONSERVATIVE (fp-border->FP, fn-border->FN):")
print("  ", recompute(False, True))
print("Adjudicated, borderline GENEROUS (fp-border->TP, fn-border->TN):")
print("  ", recompute(True, False))
print("Adjudicated, borderline SPLIT-as-errors is conservative bound above; midpoint is the honest headline.")

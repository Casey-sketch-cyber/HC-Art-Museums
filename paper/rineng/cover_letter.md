Dear Editors of *Results in Engineering*,

We submit our manuscript, "Safe Reinforcement Learning with Conservation-Aware Constraints for HVAC Control in Art Museums: Encoding EN 15757 Rate Limits as a Constrained MDP," for consideration as a full research paper.

The work addresses a concrete engineering problem: how to operate museum HVAC so that preventive-conservation limits for sensitive collections (the EN 15757 and ASHRAE Class A1 temperature and humidity envelopes, including the dynamic rate-of-change clauses) are respected while energy use and visitor comfort are managed. Our contribution is not the re-application of a known algorithm. It is an engineering formulation and an evaluation:

1. We encode the EN 15757 dynamic rate clauses, together with the static ASHRAE envelopes, as the cost of a Constrained Markov Decision Process. To our knowledge this is the first constrained formulation of museum HVAC that includes the rate-of-change clauses, which are the part of the standard that governs short-term mechanical damage.

2. We build and release a high-fidelity museum HVAC testbed, extending Sinergym's five-zone EnergyPlus building with five independent per-zone thermostats and active humidification, and map the zones onto distinct collection envelopes.

3. We report an honest sim-to-real reality check. The constrained controller performs well on a fast lumped-capacity simulator, and the per-zone localization of residual violations (to the hygrically incompatible bronze-storage zone) reproduces on the high-fidelity model. However, on EnergyPlus the controller does not beat a tuned fixed setpoint; we diagnose this as the energy gradient overwhelming the constraint signal, and identify the reward-conditioning problem that must be solved for deployment. We also document a concrete implementation pitfall (Lagrange-multiplier propagation across subprocess-parallel environments) that silently invalidates the constraint.

We believe the engineering framing, the released testbed, and the candid negative transfer result are useful to readers working on building energy, sustainable engineering, and applied control, and that the honest reporting of where the method does and does not work is itself a contribution to the field.

The manuscript is original, has not been published previously, and is not under consideration elsewhere. All authors have approved the submission and declare no competing interests. Code and the testbed are available for review at an anonymized repository and will be released openly upon publication.

We thank you for your consideration.

Sincerely,
He Zhao (corresponding author), on behalf of all authors
School of Art, Guilin University of Technology, Guilin 541004, China
E-mail: 2010011@glut.edu.cn

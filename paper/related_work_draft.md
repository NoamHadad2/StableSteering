# Related Work Draft

This draft is the first citation-backed version of the related-work section for StableSteering. It is intentionally cautious. The current repository supports a systems-platform claim more strongly than an algorithmic-superiority claim, so the goal of this section is to position the project accurately rather than aggressively.

## 1. Comparison axes

Prior diffusion-control work differs mainly in what users can control, when the intervention occurs, and whether preference information updates the model or only the interaction state. Organizing the literature around these axes produces a cleaner comparison than treating all adjacent systems as one flat family.

## 2. Control surface: prompts, instructions, and edit guidance

Several influential papers show that diffusion outputs can be controlled through prompt editing, cross-attention manipulation, instruction following, or guided image editing. Prompt-to-Prompt demonstrates cross-attention control for prompt-based editing [@hertz2022prompttoprompt]. InstructPix2Pix learns to follow editing instructions [@brooks2023instructpix2pix]. Imagic optimizes text embeddings for editing real images [@kawar2023imagic]. SDEdit treats control as guided image editing through a diffusion prior [@meng2022sdedit].

The most relevant comparison axis for the present paper is not raw image quality but how these systems organize user interaction. In the prompt-centric, instruction-centric, and edit-guided systems above, prompt text or editing instructions remain the primary control surface. By contrast, StableSteering centers a persistent session with explicit rounds, candidate comparisons, structured preference capture, and replayable multi-round history.

## 3. Intervention locus: conditioning and internal control paths

Another nearby cluster studies steering diffusion outputs by manipulating latent or text-conditioned representations directly, or by adding specialized control mechanisms. DiffusionCLIP shows that diffusion models can support text-guided image manipulation by linking CLIP semantics to diffusion trajectories [@kim2022diffusionclip]. Imagic likewise highlights the usefulness of operating on text embeddings rather than only rewriting user prompts [@kawar2023imagic]. ControlNet extends this axis by adding spatial conditioning pathways to a pretrained text-to-image model [@zhang2023controlnet].

StableSteering fits this cluster at the implementation level but with a narrower claim. The repository maintains a steering state and applies it through the generation path as a compact control abstraction, then updates that state from normalized user feedback. By contrast, the methods above contribute new conditioning or editing mechanisms, whereas StableSteering contributes an interactive loop that can host and compare such mechanisms inside a replayable system.

## 4. Preference signals: model optimization versus session updates

Preference-guided optimization papers use feedback to update the model or policy itself. DPOK uses preference information to fine-tune text-to-image diffusion behavior [@fan2024dpok]. Curriculum DPO further develops diffusion preference optimization through a staged training process [@croitoru2025curriculumdpo]. These works are directly relevant because they show that preference signals can shape generation in principled ways.

StableSteering’s present contribution is different in locus and scope. The repository updates only the session state and selection policy across rounds; it does not update model parameters during interaction. By contrast, the preference-optimization papers above modify the learned generator or its training objective, whereas StableSteering contributes infrastructure for collecting, replaying, and comparing structured preference signals inside an interactive loop.

## 5. Traceability and replayable artifacts

DiffusionDB is relevant because it reveals how real users interact with text-to-image systems in practice, including prompt diversity and hyperparameter variation [@wang2023diffusiondb]. That work reinforces the broader motivation for StableSteering: prompt-based control is powerful yet often indirect and difficult to reason about. StableSteering’s strongest differentiator is not simply another control method but the way it packages interaction as a replayable, inspectable systems artifact. By contrast, much prior work emphasizes control quality or alignment performance, whereas StableSteering preserves per-session traces, diagnostics, replay views, and HTML reports that make the interaction process inspectable after the fact.

## 6. Practical positioning

The current defensible novelty claim is integrative rather than absolute. StableSteering combines:

- prompt-first session creation
- explicit multi-round candidate generation
- configurable user feedback modes
- persistent steering state and incumbent carry-forward
- replayable artifacts, trace bundles, and diagnostics
- a runnable real-GPU backend with checked-in example output

That is a credible systems-platform contribution. It is not yet evidence that StableSteering defines the best steering algorithm, the best user interface, or the first system of its kind. The paper should explicitly avoid "first" language until the bibliography grows and closer adjacent systems are compared more comprehensively.

## References used in this draft

- [@rombach2022ldm]
- [@ho2022cfg]
- [@hertz2022prompttoprompt]
- [@brooks2023instructpix2pix]
- [@kim2022diffusionclip]
- [@kawar2023imagic]
- [@fan2024dpok]
- [@wang2023diffusiondb]

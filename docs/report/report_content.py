"""Content for the Pipeline Lab standalone research report.

Structure follows Addendum F (Chapters 1-5, 40-45 pages). Style follows
the honours writing rules: South African English, third person, final
thesis tense, no em dashes, no intensifiers, every heading preceded by
an introductory paragraph.

Citations are drawn only from the verified pool in
'Chapter 2 - 3  _  22 June 2026 B1.docx'. Nothing is cited from memory.

Content is a list of (kind, text) pairs:
  h1/h2/h3  headings
  p         body paragraph
  b         bullet
  tbl       table, text is (caption, [[row],[row]]) with header first
  fig       figure, text is (filename, caption)
  pg        page break
"""

CONTENT = [

# ===================== TITLE PAGE ==================================
("title", "Measuring the Effect of Preprocessing Choices on Tabular Model Performance"),
("subtitle", "The design, development and evaluation of Pipeline Lab, "
             "a reproducible experimentation system"),
("titlemeta", [
    "ITRI 671 Research Project",
    "",
    "Colile Sibanda (56543115)",
    "",
    "BSc Honours in Computer Science and Information Technology, 2026",
    "",
    "Supervisor: Prof Imelda Smit",
    "",
    "North-West University, Vanderbijlpark Campus",
    "",
    "October 2026",
]),
("pg", ""),

# ===================== ABSTRACT ====================================
("h1", "Abstract"),
("p", "Preprocessing decisions are made before every tabular model is trained, yet "
      "practitioners have limited controlled evidence about which of them change the outcome. "
      "This study designed, built and applied Pipeline Lab, an experimentation system that "
      "measures the effect of five preprocessing components (encoding, imputation, scaling, "
      "feature selection and hyperparameter tuning) on four model families and records the "
      "computational cost of every measurement. The system demonstrates the absence of leakage "
      "rather than assuming it, varies each factor alone against a declared baseline, and "
      "writes every run to an append-only record of 89 typed columns."),
("p", "The study produced 4,761 experimental runs across 31 datasets in 85.5 hours of measured "
      "compute. Of 167 statistical cells, 34 contrasts survived Holm correction. Most "
      "preprocessing choices produced no detectable difference, and the differences that "
      "appeared belonged to particular model families rather than to pipelines in general: "
      "scaling affected the support vector machine and logistic regression and left tree "
      "ensembles unchanged, while hyperparameter tuning consumed 68 per cent of the compute for "
      "a single surviving result. The encoding comparison is reported as untested rather than "
      "null, because 54 of its 64 classification cells contain no categorical features."),
("p", "The principal finding concerns reliability. Under a second random seed only 35 per cent "
      "of the imputation arm's contrasts reproduced, and only 8 per cent survived all three "
      "seeds. Widening that arm from nine datasets to fourteen raised reproduction to 59 per "
      "cent, identifying registry size as a measurable cause of the instability. A prediction "
      "about the strongest scaling result, registered before its datasets were scored, was not "
      "confirmed on five unseen datasets and is reported as such. In both replicated arms, "
      "reproducibility tracked effect size, which gives practitioners a usable threshold for "
      "deciding which differences to trust."),
("h1", "Chapter 1: Introduction"),
("p", "A practitioner who sets out to train a model on tabular data makes a series of "
      "decisions before any learning takes place. Categorical columns must be converted to "
      "numbers, missing values must be filled or removed, features may be placed on a common "
      "scale, some features may be discarded, and model settings may be searched for rather "
      "than left at their defaults. Each of these decisions has several defensible options, "
      "and the choice between them is often made by habit or by following whatever the "
      "previous project did. The question of which decisions actually change the result, and "
      "by how much, is asked less often than it should be."),
("p", "This study addressed that question by building an instrument to answer it and then "
      "applying that instrument across a registry of datasets. The project produced Pipeline "
      "Lab, a system that composes preprocessing techniques into evaluation pipelines, varies "
      "one component at a time while holding the others fixed, and records what every run "
      "produced along with what it cost. The system is the central contribution of the study; "
      "the empirical findings follow from it."),
("p", "This chapter introduces the research problem and the reasoning behind the study. It "
      "defines the concepts central to the work, states the problem and the objectives that "
      "follow from it, outlines the methodology and the project management approach, "
      "addresses ethical considerations, and closes with the structure of the remaining "
      "chapters."),

("h2", "1.1 Concepts central to the study"),
("p", "Four concepts recur throughout the report and carry specific meanings in this context. "
      "Each is introduced here and developed further in the literature review."),
("h3", "1.1.1 Preprocessing"),
("p", "Preprocessing refers to the transformations applied to data between collection and "
      "model fitting. García, Luengo and Herrera (2015) treat preprocessing as a field in its "
      "own right rather than as preparation incidental to modelling, covering normalisation, "
      "discretisation, imputation and feature selection. Kuhn and Johnson (2013) make a "
      "similar case from an applied perspective, arguing that the preparation of predictors "
      "frequently determines model performance more than the choice of algorithm. In this "
      "study preprocessing is limited to five components, each with a fixed set of techniques."),
("h3", "1.1.2 Data leakage"),
("p", "Leakage occurs when information from outside the training data influences the model, "
      "producing performance estimates that cannot be reproduced in deployment. Kaufman, "
      "Rosset, Perlich and Stitelman (2012) formulated the problem and catalogued the forms it "
      "takes, including the case where a preprocessing step is fitted on the full dataset "
      "before cross-validation splits it. Kapoor and Narayanan (2023) traced leakage through "
      "published machine-learning research across multiple fields and found it widespread, "
      "which indicates that the risk is practical rather than theoretical. Leakage is "
      "relevant to this study because feature selection and hyperparameter tuning are the two "
      "components most exposed to it."),
("h3", "1.1.3 One-factor-at-a-time experimentation"),
("p", "A one-factor-at-a-time design varies a single independent variable while holding the "
      "remainder at declared values. The design cannot detect interactions between factors, "
      "which is its principal weakness, but it allows any observed difference to be "
      "attributed to the factor that was varied. This study adopted the design because "
      "attribution was the primary concern and because the number of configurations in a full "
      "factorial design over five components would have exceeded the available compute."),
("h3", "1.1.4 Reproducible experimentation"),
("p", "Reproducibility in this context means that a recorded result can be traced to the "
      "conditions that produced it: the data, the seed, the software versions and the code "
      "revision. Xin, Miao, Parameswaran and Polyzotis (2021) analysed production machine "
      "learning pipelines and found that the operational detail surrounding a model is rarely "
      "recorded in a form that supports later analysis. Strasser and Klettke (2024) argued "
      "specifically for transparency in preprocessing, noting that the steps applied to data "
      "are often the least documented part of a pipeline."),

("h2", "1.2 Problem description and objectives"),
("p", "The problem this study addressed has both an empirical and a methodological dimension, "
      "and the two are connected. This section states the problem, the research question and "
      "the objectives that follow from them."),
("h3", "1.2.1 Research problem"),
("p", "Evidence about preprocessing effects exists but is difficult to compare across studies. "
      "Ahsan, Mahmud, Saha, Gupta and Siddique (2021) examined scaling methods across several "
      "algorithms and reported that the effect depends on the algorithm, while Jadhav, Pramod "
      "and Ramanathan (2019) and Jäger, Allhorn and Bießmann (2021) compared imputation "
      "methods and reached conclusions that depend on the datasets and missingness conditions "
      "examined. These studies each hold different elements constant, use different "
      "evaluation protocols, and report different measures, which makes their results hard to "
      "place beside one another."),
("p", "Three difficulties make a credible comparison hard to produce. The first is leakage: a "
      "preprocessing step fitted outside the cross-validation fold inflates the score without "
      "raising an error, and the inflation is invisible in the reported result. The second is "
      "confounding: when several pipeline stages change together, no single stage can be "
      "credited with the difference. The third is incomplete recording: without the seed, the "
      "software versions, the data version and the code revision, a result cannot be "
      "re-derived or audited later."),
("h3", "1.2.2 Research question"),
("p", "The study was guided by one question: to what extent do encoding, imputation, scaling, "
      "feature selection and hyperparameter tuning each affect the predictive performance of "
      "common models on tabular data, and what does each one cost to apply?"),
("h3", "1.2.3 Aim"),
("p", "The aim of the study was to design and build a system capable of measuring "
      "single-factor preprocessing effects without leakage and with full provenance, and to "
      "apply that system across a dataset registry in order to establish which effects are "
      "supportable and at what computational cost."),
("h3", "1.2.4 Objectives"),
("p", "The aim was pursued through five objectives:"),
("b", "Build an experimentation engine that composes preprocessing techniques into "
      "leakage-safe evaluation pipelines and records each run in full."),
("b", "Implement a one-factor-at-a-time design across five preprocessing components and four "
      "model families."),
("b", "Apply a pre-committed statistical framework that reports an effect size with every "
      "comparison and declines to report pairwise results the global test does not license."),
("b", "Measure the computational cost of each component alongside the evidence it produces."),
("b", "Establish whether the results depend on the evaluation protocol used to obtain them."),

("h2", "1.3 Research methodology"),
("p", "The study followed a positivist paradigm and a quantitative, experimental methodology. "
      "Park, Konge and Artino (2020) describe positivism as proceeding from the position that "
      "an observable reality can be measured and that findings are established through "
      "controlled observation, which matches a study in which a measurable quantity is "
      "compared across controlled conditions. The paradigm choice is justified more fully in "
      "Chapter 2."),
("p", "Data were generated rather than collected from participants. Each experimental run "
      "produced numerical performance measures under stratified ten-fold cross-validation, "
      "with a repeated holdout protocol used as a secondary check. Analysis followed the "
      "framework recommended by Demšar (2006) for comparing methods across multiple datasets: "
      "a Friedman test across all levels of a factor, followed by pairwise tests against the "
      "baseline only where the global test licenses them, with correction for multiple "
      "comparisons."),
("p", "The artefact was developed iteratively. Each development cycle produced a working "
      "engine capable of running a sweep, the sweep was run, and the results together with any "
      "defects encountered informed the next cycle. Three cycles were completed, and the "
      "reasoning that led from the second to the third is discussed in Chapter 4."),

("h2", "1.4 Scope, limitations and risk"),
("p", "The study was bounded deliberately so that the design would remain attributable within "
      "the available time and compute. The scope and the principal risks are stated here and "
      "revisited in Chapter 5 once the results allow them to be assessed."),
("p", "The study covered supervised learning on tabular data, both classification and "
      "regression, using four model families: logistic regression, the support vector machine, "
      "random forest and gradient boosting. Deep learning, time series, text and image data "
      "fell outside the scope. Grinsztajn, Oyallon and Varoquaux (2022) and Shwartz-Ziv and "
      "Armon (2022) both report that tree-based methods remain competitive with neural "
      "approaches on tabular problems, which supports restricting attention to the classical "
      "families."),
("p", "Three risks were identified at the outset. The first was that the compute required "
      "would exceed what was available, which was mitigated by measuring the cost of each "
      "component before committing to a full sweep. The second was that defects in the engine "
      "would corrupt results, which was mitigated by an extensive test suite and by treating "
      "the run record as append-only. The third was that the dataset registry would prove too "
      "small to support the statistical tests, which materialised in part and is discussed in "
      "Chapter 4."),

("h2", "1.5 Ethical considerations"),
("p", "The study involved no human or animal participants, no personal data and no "
      "intervention in any organisation. All datasets were obtained from public repositories "
      "(scikit-learn, OpenML and the UCI repository) that distribute them for research use, "
      "each was used under its licence, and no attempt was made to re-identify individuals in "
      "any record. The ITRI 671 research ethics form was completed on that basis and signed by "
      "the researcher and the study leader on 31 August 2026 (Appendix A). It records no use of "
      "people as a source of data, no need for permission from another party, and no "
      "foreseeable risk to participants, the environment or the university."),
("p", "The researcher completed modules 1 to 3 of the TRREE training programme in research "
      "ethics evaluation, covering an introduction to research ethics, research ethics "
      "evaluation and informed consent, with certificates released on 30 August 2026, and "
      "signed the NWU Code of Conduct for Researchers on 31 August 2026 (Appendix B). Both "
      "were completed before the first experimental run on 12 October 2026."),
("p", "Ethical obligations nonetheless applied to the conduct of the research itself. Passi "
      "and Jackson (2018) describe accountability in data science as resting on the ability to "
      "account for how a result was produced rather than on the result alone. The study "
      "treated that obligation as binding in two respects: results that were later found to be "
      "artefacts were withdrawn and reported as such rather than quietly dropped, and null "
      "results were reported with the same weight as positive ones."),

("h2", "1.6 Report structure"),
("p", "The remainder of the report is organised into four chapters. Chapter 2 sets out the "
      "research methodology, considers the paradigms available to a computing study, and "
      "justifies the design adopted. Chapter 3 reviews the literature on preprocessing "
      "effects, leakage and statistical comparison, and explains how that literature shaped "
      "the study. Chapter 4 describes the artefact, the development cycles, the experiments "
      "conducted and the results obtained. Chapter 5 evaluates the study against its "
      "objectives, states its contributions and limitations, and reflects on the process "
      "followed."),
("p", "This chapter has introduced the problem that motivated the study, defined the concepts "
      "on which it rests, and stated the question and objectives that guided it. Chapter 2 "
      "turns to the methodological choices through which those objectives were pursued."),
("pg", ""),

# ===================== CHAPTER 2 ===================================
("h1", "Chapter 2: Research Methodology"),
("p", "The focus of this project was to measure how far five preprocessing decisions affect "
      "the performance of models trained on tabular data, and to do so with an instrument "
      "whose results can be trusted and traced. This chapter addresses the methodological part "
      "of that focus by setting out the paradigm, methodology and methods through which the "
      "measurement was carried out."),
("p", "The chapter considers the research paradigms available to a computing study and "
      "explains which was adopted and why, describes the methodology and the steps that "
      "establish rigour, sets out the research methods in the order in which they were "
      "applied, and presents the research design in visual form."),
("p", "The sections that follow move from the philosophical position of the study, through the "
      "methodology and methods, to the design that combines them."),

("h2", "2.1 Research paradigms"),
("p", "A paradigm expresses what the researcher takes to exist and what counts as knowledge of "
      "it. Three paradigms are commonly applied in computing research, and the suitability of "
      "each to this study is considered in turn."),
("h3", "2.1.1 Positivism"),
("p", "Positivism holds that an observable reality exists independently of the observer and "
      "that knowledge of it is established through measurement and controlled comparison. "
      "Park, Konge and Artino (2020) note that the paradigm supports hypothesis testing and "
      "the quantification of relationships between variables. This study measured a numerical "
      "quantity, model performance, under conditions that were controlled by design and "
      "repeated with a fixed random seed. The measurement is independent of the researcher in "
      "the sense that another researcher running the same configuration on the same data "
      "obtains the same result. Positivism was therefore adopted as the paradigm for the "
      "study."),
("h3", "2.1.2 Interpretivism"),
("p", "Interpretivism proceeds from the position that social reality is constructed through "
      "the meanings participants attach to it, and that knowledge is produced by interpreting "
      "those meanings in context. The paradigm suits studies of how practitioners experience "
      "or reason about their work. Passi and Jackson (2018) applied an interpretive approach "
      "to data science teams and produced an account of how trust is negotiated between "
      "collaborators, which a measurement study could not have produced. The present study "
      "asked what a preprocessing choice does to a score rather than how practitioners "
      "understand that choice, so interpretivism was not adopted."),
("h3", "2.1.3 Critical realism"),
("p", "Critical realism distinguishes between events that are observed and the underlying "
      "mechanisms that generate them. Bhaskar (1975) set out the position, and Mingers (2004) "
      "developed its application to information systems, arguing that explanation requires "
      "identifying the mechanism responsible for an observed regularity rather than recording "
      "the regularity alone. The paradigm was not adopted as the overall position of the "
      "study, because the research question concerns the size of an effect rather than the "
      "structure that produces it. Its influence is nonetheless visible in one part of the "
      "work: where an unexpected result appeared, the study investigated the mechanism behind "
      "it rather than reporting the observation alone, and Chapter 4 describes two cases in "
      "which that investigation changed the conclusion."),

("h2", "2.2 Research methodology"),
("p", "A quantitative experimental methodology was adopted, in which an independent variable "
      "is manipulated under controlled conditions and the effect on a dependent variable is "
      "measured. The independent variable in each experiment was the technique applied at one "
      "preprocessing component, the dependent variable was model performance, and the control "
      "was achieved by holding the remaining four components at declared baseline values."),
("p", "The methodology is only as trustworthy as the measures taken to establish rigour. Four "
      "such measures were adopted, and each is described in the subsections that follow."),
("h3", "2.2.1 Internal validity through attribution"),
("p", "Internal validity in this study rests on the ability to attribute an observed difference "
      "to the factor that was varied. The one-factor-at-a-time design supports that attribution "
      "directly, and the configuration layer of the artefact enforces it: a configuration that "
      "pins the component being varied is refused rather than run. The design cannot detect "
      "interactions between components, which is a limitation of the approach rather than a "
      "flaw in its execution, and it is acknowledged in Chapter 5."),
("h3", "2.2.2 Internal validity through the absence of leakage"),
("p", "A pipeline that leaks produces inflated scores that are indistinguishable from genuine "
      "improvement. Kaufman et al. (2012) describe the preprocessing case specifically: a "
      "transformation fitted on all available data before the data are split carries "
      "information from the test partition into the training partition. The study addressed "
      "this by composing every transformation inside the cross-validation loop and then "
      "demonstrating, through instrumentation described in Chapter 4, that no transformation "
      "was fitted on data outside its training fold."),
("h3", "2.2.3 Reliability through controlled repetition"),
("p", "Reliability was addressed through a fixed random seed applied throughout, stratified "
      "ten-fold cross-validation as the primary protocol, and a secondary protocol of thirty "
      "repeated holdout splits applied to the larger datasets. Kohavi (1995) compared "
      "cross-validation with bootstrap estimation and recommended stratified ten-fold "
      "cross-validation as the preferred choice for accuracy estimation on datasets of "
      "moderate size, which is the basis on which the primary protocol was selected."),
("h3", "2.2.4 Statistical rigour"),
("p", "Comparing several methods across several datasets raises the probability of a false "
      "positive unless the comparison is corrected. Demšar (2006) recommended a non-parametric "
      "procedure for this situation: a Friedman test across all methods, followed by post-hoc "
      "pairwise tests only when the global test is significant. García, Fernández, Luengo and "
      "Herrera (2010) extended the analysis of such procedures and examined their statistical "
      "power, which is relevant to this study because a power limitation was encountered and "
      "is reported in Chapter 4. Benavoli, Corani, Demšar and Zaffalon (2017) later proposed "
      "Bayesian alternatives to null-hypothesis testing for this setting; the frequentist "
      "procedure was retained here because it is the convention in the comparative literature "
      "the study is positioned against."),

("h2", "2.3 Research methods"),
("p", "The methods set out below are those applicable to an experimental study within a "
      "positivist paradigm. They are presented in the order in which they were applied."),
("h3", "2.3.1 Dataset selection"),
("p", "Datasets were drawn from scikit-learn's bundled collections and from OpenML, which "
      "distribute datasets for research use. Selection favoured variety in size, feature count, "
      "task type and the presence of categorical features, so that an effect appearing on one "
      "kind of dataset but not another would be visible. Twenty-five datasets were used in "
      "total, covering both classification and regression."),
("h3", "2.3.2 Experimental procedure"),
("p", "Each experiment, referred to as a sweep, varied one component across its available "
      "techniques while holding the others at baseline, and ran every combination of technique, "
      "dataset and model. A single run consisted of one such combination evaluated under the "
      "chosen protocol, and produced one row in the run record."),
("h3", "2.3.3 Controlled missingness injection"),
("p", "The imputation component could not be examined usefully on data that contains no "
      "missing values. Little and Rubin (2019) distinguish between data missing completely at "
      "random, missing at random and missing not at random, and the distinction matters "
      "because imputation methods respond differently to each. The study implemented injection "
      "of missing values under the first two mechanisms at controlled rates, which allowed the "
      "imputation component to be examined under known conditions rather than whatever "
      "conditions the datasets happened to present."),
("h3", "2.3.4 Analysis procedure"),
("p", "Analysis followed the Demšar (2006) framework described in section 2.2.4. Where the "
      "global test was significant, each non-baseline technique was compared with the baseline "
      "using a Wilcoxon signed-rank test, and the resulting p-values were corrected using the "
      "Holm procedure. An effect size accompanied every comparison, expressed as the median "
      "difference with a bootstrapped confidence interval and the count of datasets on which "
      "each technique improved on the baseline."),

("h2", "2.4 Research design"),
("p", "The design combines the paradigm, methodology and methods described above into a single "
      "procedure, represented in Figure 2.1. The figure shows the path from a configuration "
      "to a recorded result and the points at which the controls described in section 2.2 "
      "apply."),
("fig", ("design_flow.png",
         "Figure 2.1: The research design. A configuration declares one varied component and "
         "a baseline for the rest; the engine composes a leakage-safe pipeline per run, "
         "evaluates it under cross-validation, and appends the result with its cost and "
         "provenance to the run record, from which the statistical analysis is computed.")),
("p", "The design operates as a loop rather than a single pass. A sweep produces results, the "
      "results are analysed, and where the analysis exposes a defect in the instrument the "
      "defect is corrected and the affected sweep is run again. Chapter 4 reports two "
      "occasions on which this occurred."),
("p", "This chapter has set out the paradigm adopted and the reasons for preferring it, the "
      "methodology and the four measures through which rigour was pursued, the methods applied "
      "and the design that combines them. Chapter 3 examines the literature that informed "
      "these choices and identifies the gap the study addresses."),
("pg", ""),

# ===================== CHAPTER 3 ===================================
("h1", "Chapter 3: Literature Review"),
("p", "The focus of this project was to measure the effect of five preprocessing decisions on "
      "tabular model performance using an instrument whose results can be traced and trusted. "
      "This chapter addresses the theoretical part of that focus by examining what is already "
      "known about those effects and about the conditions under which such measurements are "
      "credible."),
("p", "The chapter reviews four bodies of literature: work on preprocessing and its effect on "
      "performance, work on data leakage, work on the statistical comparison of methods across "
      "datasets, and work on reproducibility in machine learning pipelines. It closes by "
      "explaining how this literature shaped the study."),
("p", "The sections that follow are organised by the four concepts introduced in Chapter 1, "
      "with a summary at the end of each."),

("h2", "3.1 Preprocessing and model performance"),
("p", "Preprocessing is treated in the literature both as a practical necessity and as a "
      "subject of study in its own right. This section examines the general treatments first "
      "and then the evidence relating to individual components."),
("p", "García, Luengo and Herrera (2015) provide the most comprehensive treatment, covering "
      "normalisation, discretisation, imputation and feature selection as a coherent field "
      "with its own methods and evaluation concerns. Kuhn and Johnson (2013) approach the same "
      "territory from applied predictive modelling and argue that the preparation of "
      "predictors often matters more to the final result than the choice of algorithm. Both "
      "works describe what each technique does and when it is appropriate, but neither "
      "provides controlled measurement of how much each technique changes performance when the "
      "remainder of the pipeline is held constant."),
("p", "On scaling, Ahsan, Mahmud, Saha, Gupta and Siddique (2021) compared several scaling "
      "methods across a range of algorithms and reported that the benefit depends on the "
      "algorithm rather than holding generally. The theoretical expectation agrees. Methods "
      "that depend on distances between points or on gradient magnitudes are sensitive to the "
      "relative scale of features, while methods that split on one feature at a time are not. "
      "Cortes and Vapnik (1995) set out the support vector machine, whose reliance on inner "
      "products makes it the clearest case of scale sensitivity, and Breiman (2001) introduced "
      "random forests, whose splitting procedure is unaffected by monotone transformations of "
      "individual features."),
("p", "On imputation, the literature is more divided. Troyanskaya, Cantor, Sherlock, Brown, "
      "Hastie, Tibshirani, Botstein and Altman (2001) introduced nearest-neighbour imputation "
      "and reported it superior to simpler substitutions on microarray data. Van Buuren and "
      "Groothuis-Oudshoorn (2011) developed multiple imputation by chained equations, and "
      "Stekhoven and Bühlmann (2012) proposed a random-forest-based alternative for mixed-type "
      "data. Comparative studies reach different conclusions. Jadhav, Pramod and Ramanathan "
      "(2019) found nearest-neighbour imputation strongest on the numeric datasets they "
      "examined, while Jäger, Allhorn and Bießmann (2021) benchmarked a wider range and found "
      "that the best method depends on the dataset, the missingness mechanism and the "
      "downstream model. Emmanuel, Maupong, Mpoeleng, Semong, Mphago and Tabona (2021) survey "
      "the area and note that comparisons are frequently conducted under missingness "
      "conditions that are neither controlled nor reported."),
("p", "On hyperparameter tuning and automated pipeline construction, Feurer, Klein, "
      "Eggensperger, Springenberg, Blum and Hutter (2015) and Olson and Moore (2016) both "
      "demonstrate systems that search over preprocessing and model configurations jointly. "
      "These systems optimise the pipeline rather than measure the contribution of its parts, "
      "so they answer a different question from the one posed here. Wijesinghe (2025) "
      "describes an automated preprocessing pipeline aimed at improving performance, which "
      "again treats preprocessing as something to optimise rather than to attribute."),
("p", "Fernández-Delgado, Cernadas, Barro and Amorim (2014) conducted a large comparison of "
      "classifiers across many datasets and established the value of breadth in this kind of "
      "study, while also showing how much a conclusion depends on the set of datasets "
      "examined. Taken together, the preprocessing literature establishes that these choices "
      "matter and that the effects are conditional, but leaves open the question of how large "
      "each effect is when measured under identical conditions with the rest of the pipeline "
      "held fixed."),

("h2", "3.2 Data leakage"),
("p", "The credibility of any preprocessing comparison depends on whether leakage has been "
      "excluded, which makes this literature directly relevant to the design of the "
      "instrument."),
("p", "Kaufman, Rosset, Perlich and Stitelman (2012) gave the problem its formulation, "
      "describing leakage as the introduction of information about the target that would not "
      "legitimately be available at prediction time, and catalogued the forms it takes. Among "
      "these is the case central to this study: a preprocessing step fitted on the complete "
      "dataset before cross-validation, which allows information from the test partition to "
      "influence the training partition. The resulting estimate is optimistic, and nothing in "
      "the output indicates that this has happened."),
("p", "Evidence that the problem is widespread came later. Kapoor and Narayanan (2023) "
      "examined machine-learning-based research across a range of scientific fields and found "
      "leakage recurring in published work, with the affected results frequently failing to "
      "reproduce. Teschendorff (2019) made a similar observation for omic data science, "
      "listing leakage among the common pitfalls that produce irreproducible findings. Neither "
      "study suggests that the researchers involved were careless. The point is rather that "
      "leakage is easy to introduce and difficult to notice."),
("p", "This literature led the study to treat leakage as something to be demonstrated absent "
      "rather than asserted absent. The distinction matters, because a pipeline that is "
      "believed to be leakage-safe and a pipeline that is shown to be leakage-safe produce the "
      "same output, and only the second provides evidence."),

("h2", "3.3 Statistical comparison across datasets"),
("p", "Comparing techniques across several datasets requires a procedure that controls the "
      "error rate across the whole family of comparisons, and the literature provides an "
      "established one."),
("p", "Demšar (2006) set out the procedure now widely used: a Friedman test to establish "
      "whether the methods differ at all, followed by post-hoc pairwise tests only when the "
      "global test is significant. The approach is non-parametric, which suits performance "
      "measures that are not normally distributed and are not comparable in absolute terms "
      "across datasets. García, Fernández, Luengo and Herrera (2010) extended the treatment "
      "and analysed the power of the available procedures, noting that the number of datasets "
      "governs what can be detected. Benavoli, Corani, Demšar and Zaffalon (2017) later argued "
      "for Bayesian alternatives, on the grounds that null-hypothesis tests answer a question "
      "slightly different from the one researchers intend to ask."),
("p", "Two points from this literature bear directly on the present study. The first is that a "
      "non-significant global test does not license pairwise claims, which the study enforced "
      "in software rather than by convention. The second concerns power. Because the Wilcoxon "
      "signed-rank test on a small number of paired datasets has a smallest attainable "
      "p-value determined by the number of pairs, a correction applied across several "
      "comparisons can place the achievable minimum above the significance threshold. This "
      "consequence follows from the power analysis of García et al. (2010) and is reported as "
      "an encountered limitation in Chapter 4."),

("h2", "3.4 Reproducibility and the recording of experiments"),
("p", "The final body of literature concerns what must be recorded for a computational result "
      "to be auditable, and it shaped the design of the run record."),
("p", "Xin, Miao, Parameswaran and Polyzotis (2021) analysed production machine learning "
      "pipelines and found that operational detail is rarely retained in a form that supports "
      "later analysis, with the consequence that questions arising after the fact require the "
      "work to be repeated. Strasser and Klettke (2024) address preprocessing specifically and "
      "argue for transparency in the steps applied to data, noting that preprocessing is often "
      "the least documented stage of a pipeline. Pedregosa et al. (2011) describe scikit-learn, "
      "whose pipeline abstraction provides the mechanism this study used to compose "
      "transformations inside the cross-validation loop."),
("p", "Passi and Jackson (2018) approach the same territory from a different direction, "
      "arguing that accountability in data science rests on being able to account for how a "
      "result was produced. Their study is interpretive rather than quantitative, but the "
      "conclusion applies to this work: a record that captures only the score cannot support a "
      "later question about the conditions that produced it."),

("h2", "3.5 How the literature guided the study"),
("p", "The four bodies of literature shaped different parts of the design, and the connections "
      "are set out here."),
("p", "The preprocessing literature established that effects exist and are conditional on the "
      "model and the data, which justified a design that varies one component at a time across "
      "several model families rather than reporting a single overall verdict. It also supplied "
      "the specific expectations against which the results of this study can be compared. "
      "Scaling should matter for the support vector machine and not for tree ensembles, and "
      "the best imputer should depend on the missingness conditions."),
("p", "The leakage literature determined that the instrument would need to demonstrate the "
      "absence of leakage rather than assert it, which led to the instrumentation described in "
      "Chapter 4. The statistical literature supplied the analysis procedure and, through its "
      "treatment of power, anticipated the limitation the study encountered. The "
      "reproducibility literature determined the scope of the run record, in particular the "
      "decision to store cost and data characteristics alongside performance so that later "
      "questions could be answered without repeating the work."),
("p", "Across all four bodies, the gap this study addresses is consistent. The effects of "
      "preprocessing choices have been examined technique by technique, under conditions that "
      "differ between studies, without a common instrument that holds the remainder of the "
      "pipeline fixed and records what each measurement cost to obtain."),
("p", "This chapter has reviewed the literature on preprocessing effects, leakage, statistical "
      "comparison and reproducibility, and has shown how each informed the design of the "
      "study. Chapter 4 describes the artefact built on these foundations and reports the "
      "results obtained from it."),
("pg", ""),

# ===================== CHAPTER 4 ===================================
("h1", "Chapter 4: Empirical Study"),
("p", "The focus of this project was to measure how far five preprocessing decisions affect "
      "tabular model performance, and to do so with an instrument whose results can be traced "
      "and trusted. This chapter addresses the empirical part of that focus by describing the "
      "artefact that was built, the way it was developed, the experiments conducted with it "
      "and the results obtained."),
("p", "The chapter describes the system and its components, sets out the three development "
      "cycles and the reflection that led from one to the next, explains the experimental "
      "procedure and the sweeps that were run, analyses the results factor by factor, and "
      "reports the findings together with the measures that establish their trustworthiness."),
("p", "The sections that follow move from the artefact, through its development and "
      "application, to the results it produced."),

("h2", "4.1 Description of the artefact"),
("p", "Pipeline Lab consists of three parts: an engine that runs experiments and records "
      "them, a run record that stores the results, and a browser interface that reads the "
      "record. The parts are described in turn, after an overview of how they fit together."),
("fig", ("system_architecture.png",
         "Figure 4.1: The structure of Pipeline Lab. The engine composes and evaluates "
         "pipelines and writes to the run record; the interface reads the same record without "
         "modifying it; adapters allow the interface to drive the two earlier codebases.")),
("h3", "4.1.1 The engine"),
("p", "The engine is a Python package of 27 modules organised by responsibility: "
      "configuration, dataset loading, component factories, pipeline composition, evaluation "
      "protocols, statistics, provenance capture and storage. A configuration file declares "
      "which component varies, which techniques it takes, which datasets and models to use, "
      "and the baseline at which the remaining components are held. The engine expands this "
      "into individual runs and executes them in sequence."),
("p", "Composition is where the leakage guarantee is established. Each run builds a "
      "scikit-learn pipeline (Pedregosa et al., 2011) in which numeric features are imputed "
      "and scaled, categorical features are imputed and encoded, the combined result passes "
      "through the feature selector, and the model sits at the end. Because every "
      "transformation is a pipeline step, scikit-learn fits it on the training portion of each "
      "fold and applies it to the held-out portion, so the structure itself prevents the "
      "leakage described by Kaufman et al. (2012)."),
("p", "Two stages sit outside the composed pipeline for reasons that are recorded in the "
      "code. Row deletion changes the number of samples, which a pipeline transformer may not "
      "do, so the evaluator applies it before folds are constructed. Hyperparameter tuning "
      "wraps the entire composed pipeline so that feature selection is repeated inside each "
      "inner search, which prevents the selection from being fixed before the search begins."),
("h3", "4.1.2 The run record"),
("p", "Every run appends one row to a SQLite database, and no row is ever modified or "
      "removed. The row carries 89 typed columns, which fall into the groups shown in Table "
      "4.1. The scope of the record follows from the reproducibility literature discussed in "
      "section 3.4: a record that stores only the score cannot answer a later question about "
      "the conditions that produced it."),
("tbl", ("Table 4.1: The groups of information recorded for every run.",
         [["Group", "Examples", "Purpose"],
          ["Identity", "run identifier, batch, configuration name, code revision",
           "Traces a result to the code and sweep that produced it"],
          ["Factor levels", "encoding, imputation, scaling, selection, tuning, model, dataset",
           "States the condition under which the run was made"],
          ["Protocol", "protocol, outer folds, inner folds, holdout repeats, fold hash",
           "Records how the score was obtained"],
          ["Results", "accuracy, macro F1, RMSE, each with standard deviation and per-fold scores",
           "The measured outcome"],
          ["Data characteristics", "rows, features, numeric and categorical counts, missing "
           "percentage, class balance, mean absolute correlation",
           "Allows later analysis by dataset property"],
          ["Cost", "wall time, user and system CPU time, peak memory, thread count",
           "Allows the cost of a component to be compared with its benefit"],
          ["Environment", "processor, memory, operating system, Python and library versions",
           "Makes a timing measurement interpretable"],
          ["Outcome", "status, error type, error message, substitution note",
           "Distinguishes a null result from an absent one"]])),
("p", "The last group deserves emphasis. A run that cannot legitimately proceed is recorded "
      "as skipped with the reason stored, rather than omitted. The distinction between a "
      "result that was measured and found to be null, and a result that was never obtained, "
      "is preserved in the record rather than left to the reader to infer."),
("h3", "4.1.3 Components and techniques"),
("p", "The five components and their techniques are listed in Table 4.2. The baseline for "
      "each component is the technique against which the others are compared and the value at "
      "which the component is held when another component is being varied."),
("tbl", ("Table 4.2: The five preprocessing components, their techniques and baselines.",
         [["Component", "Techniques", "Baseline"],
          ["Encoding", "one-hot, ordinal, target", "one-hot"],
          ["Imputation", "row deletion, mean, median, nearest neighbour", "row deletion"],
          ["Scaling", "none, standard, min-max, robust", "none"],
          ["Feature selection", "none, chi-square, mutual information, recursive elimination, "
           "L1-based", "none"],
          ["Hyperparameter tuning", "none, grid, random, Bayesian", "none"]])),
("p", "Where a technique cannot legitimately apply, the engine substitutes a defensible "
      "alternative and records the substitution on the run. The chi-square filter, for "
      "instance, requires non-negative features and a classification target; on a regression "
      "target the engine substitutes an F-test, and on negative features it substitutes the "
      "classification F-test. Each substitution is written to the run so that it is visible in "
      "the record rather than silent."),
("h3", "4.1.4 Missingness injection"),
("p", "The imputation component required data with missing values, and most datasets in the "
      "registry contain none. The engine therefore includes an injector that introduces "
      "missing values at a controlled rate under two of the mechanisms distinguished by "
      "Little and Rubin (2019): missing completely at random, where the probability of a "
      "value being absent is independent of the data, and missing at random, where it depends "
      "on another observed column. The injector was ported from the earlier B2 codebase and "
      "verified against it, so that results from the two remain comparable."),
("h3", "4.1.5 The interface"),
("p", "A browser interface of eleven pages reads the run record and presents the catalogue of "
      "sweeps, aggregate views, trend charts and the statistical findings. It opens the "
      "database in read-only mode, so the interface cannot alter a result. The findings page "
      "re-implements the statistical framework described in section 2.2.4, and a test asserts "
      "that its output matches the engine, so that the interface cannot drift from the "
      "analysis reported here."),

("h2", "4.2 How the study arrived at this artefact"),
("p", "The system described above was the third attempt at the measurement problem rather "
      "than the first. The earlier two shaped what the final one needed to do, so the path "
      "between them forms part of the research process and is set out briefly here."),
("p", "The first cycle produced a pre-registered study of two components, scaling and "
      "imputation, across a dataset registry. It returned usable results, among them that "
      "standardisation improved support vector machine accuracy by 7.3 percentage points with "
      "a 95 per cent confidence interval of 2.5 to 12.1, and a null for imputation at a 15 "
      "per cent missing rate. Running it raised two questions it could not answer. Three of "
      "the five components were never examined, so nothing could be said about their relative "
      "importance, and the imputation null was difficult to interpret because the missingness "
      "conditions had not been controlled."),
("p", "The second cycle addressed the second question in part. It introduced controlled "
      "injection of missing values, repeated the imputation arm under known conditions, and "
      "found nearest-neighbour imputation strongest for regression below a 30 per cent "
      "missing rate. It confirmed the scaling result from the first cycle. What it did not "
      "resolve was the breadth of the design, and a further difficulty became apparent while "
      "interpreting its output: the results were held in flat files that recorded the score "
      "but not the conditions, so a question arising after a sweep had finished generally "
      "required the sweep to be run again."),
("p", "Three requirements for the third cycle followed from that experience. The design "
      "needed to cover all five components rather than two, so that the comparison between "
      "them could be made at all. Missingness needed to be controlled as a matter of course "
      "rather than added for one arm. The record needed to hold enough detail that a later "
      "question could be answered from it, which meant storing cost, data characteristics and "
      "software environment alongside the score, and distinguishing a run that was skipped "
      "for a stated reason from one that was never attempted."),
("p", "A fourth requirement came from the literature rather than from experience. The earlier "
      "cycles composed their transformations inside the cross-validation loop and were "
      "believed to be free of leakage, but neither could demonstrate it for a given run. "
      "Kapoor and Narayanan (2023) report that leakage is both common in published work and "
      "difficult to notice, so the third cycle was built so that its absence could be shown "
      "rather than assumed, through the instrumentation described in section 4.5.1."),
("p", "These four requirements define the system reported in this chapter, and they are the "
      "reason the third cycle was adopted as final. The earlier two were not discarded. Their "
      "results remain part of the research record, the interface reads all three through a "
      "common adapter so that the studies can be compared, and section 4.4.3 sets the "
      "imputation findings of this study against those of the second cycle."),
("p", "Development within the third cycle followed the same pattern at a smaller scale. Each "
      "stage produced a working system, a sweep was run, and the results were examined before "
      "the next stage began. Two of those examinations exposed defects in the instrument "
      "rather than findings about preprocessing, and both are reported in section 4.5 because "
      "they bear on how far the results can be trusted."),

("h2", "4.3 Experimentation design"),
("p", "The experiments were organised as sweeps, each varying one component. This section "
      "describes the design of those sweeps and the protocol under which runs were evaluated."),
("p", "A sweep declares the component to vary, the techniques to apply, the datasets and the "
      "models. The engine runs every combination, so a sweep over four techniques, nineteen "
      "datasets and four models produces 304 runs. Each run is evaluated under stratified "
      "ten-fold cross-validation, following Kohavi (1995). Tuning runs use nested "
      "cross-validation, with an inner three-fold loop selecting hyperparameters inside each "
      "outer training fold."),
("p", "A secondary protocol of thirty repeated 70/15/15 holdout splits was applied to the four "
      "datasets with at least 4,000 rows, where a 15 per cent test partition is large enough "
      "to be meaningful. The purpose of the secondary protocol was to establish whether the "
      "results depend on the way the data are split, which section 4.4.6 addresses."),
("p", "Table 4.3 summarises the experiments that were run. The imputation arm is larger than "
      "the others because it was repeated at six combinations of missingness mechanism and "
      "rate. The final row covers the seed replication described in section 4.4.7, which "
      "repeats the scaling arm rather than adding new experimental coverage."),
("tbl", ("Table 4.3: Experiments conducted, by component.",
         [["Component", "Sweeps", "Runs", "Measured hours"],
          ["Encoding", "2", "324", "1.5"],
          ["Imputation", "7", "2,032", "4.2"],
          ["Scaling", "6", "649", "4.5"],
          ["Feature selection", "4", "1,032", "12.5"],
          ["Hyperparameter tuning", "3", "692", "58.1"],
          ["Holdout protocol check", "1", "32", "4.8"],
          ["Total (experimental)", "23", "4,761", "85.5"],
          ["Seed replication (scaling)", "2", "608", "1.8"],
          ["Seed replication (imputation)", "6", "1,728", "2.6"],
          ["Widened imputation arm, both seeds", "12", "5,054", "24.5"],
          ["Pre-registered held-out test", "1", "20", "0.1"]])),

("h2", "4.4 Analysis of results"),
("p", "This section analyses the results component by component. Across the whole programme, "
      "167 statistical cells were tested, where a cell is one model, one metric and one sweep. "
      "Of these, 31 produced a significant global test and 34 pairwise contrasts survived Holm "
      "correction. Those counts are the starting point rather than the conclusion: section "
      "4.4.7 reports what happened when two of the arms were run again under different random "
      "seeds. Figure 4.2 shows how the results are distributed across the five components."),
("fig", ("fig1_effects_by_factor.png",
         "Figure 4.2: Statistical cells tested against cells producing a significant global "
         "test, by component. The imputation arm dominates because it was swept at six "
         "missingness settings rather than once.")),
("p", "The distribution is uneven, and the shape of that unevenness is the principal result. "
      "Encoding returned no significant result in any cell, although section 4.4.2 shows "
      "that this reflects a registry with too few categorical datasets rather than a tested "
      "null. Feature selection "
      "produced five significant global tests but no surviving pairwise contrast, for reasons "
      "examined in section 4.4.4. Imputation accounts for 23 of the 34 surviving contrasts, "
      "which reflects where experimental effort was directed rather than an intrinsic ranking "
      "of the components."),
("h3", "4.4.1 Scaling"),
("p", "Scaling produced the only rejected contrasts on the classification side and the largest "
      "observed differences in the study. All three of them belong to the support vector "
      "machine, which is the model the literature in section 3.1 predicts should be the most "
      "scale sensitive. Standard scaling improved its accuracy on 12 of 16 datasets at a "
      "Holm-corrected p-value of 0.0071, with a bootstrapped confidence interval of +0.0036 "
      "to +0.1082 that excludes zero. Minimum-maximum and robust scaling were also rejected "
      "against no scaling, both at 0.0249 and both improving on 11 of 16 datasets."),
("p", "Logistic regression shows the same effect at a size the correction will not license. "
      "Standard scaling improved it on 12 of 16 datasets at an uncorrected p-value of 0.0186, "
      "but Holm tests the smallest of three contrasts against a third of alpha, giving 0.0557. "
      "The contrast is reported here as a near miss rather than omitted, because the win count "
      "and the raw test both strengthened when the registry grew while the adjusted value "
      "crossed the threshold in the other direction. Section 4.4.7 returns to this pattern, "
      "which recurred in three separate places and says more about the resolution of the "
      "method than about scaling. Figure 4.3 shows the pattern across models."),
("fig", ("fig2_scaling_by_model.png",
         "Figure 4.3: Mean accuracy by model and scaling technique across the classification "
         "datasets. Logistic regression and the support vector machine respond to scaling; the "
         "two tree ensembles do not.")),
("p", "The direction of these results agrees with the expectation drawn from the literature in "
      "section 3.1. The support vector machine showed the largest raw movement anywhere in the "
      "study, with macro F1 rising from 0.579 without scaling to 0.787 with standard scaling "
      "on the adult dataset, and from 0.477 to 0.708 on bank-marketing. These two figures come "
      "from a supplementary sweep covering only two datasets and are reported as direct "
      "readings, but they point the same way as the tested result above."),
("p", "The tree ensembles provide the cleanest negative evidence in the study, and it is "
      "stronger than a small non-significant difference would be. In 12 of gradient "
      "boosting's 16 cells and 9 of random forest's 16, every scaling technique returned "
      "bit-identical scores, against one such cell for the support vector machine and none "
      "for logistic regression. The equality was checked on the stored per-fold scores at "
      "full precision rather than on rounded summaries, so it is exact rather than an "
      "artefact of reporting. A decision tree splits on the rank "
      "order of a feature, which no monotone rescaling alters, so the expected difference is "
      "not merely small but identically zero, and that is what the record contains. This is "
      "consistent with the splitting procedure described by Breiman (2001)."),
("p", "One result in this arm required explanation rather than reporting. On the house_16H "
      "dataset, scaling lowered linear regression error by 7.7 per cent, which conflicts with "
      "the scale invariance of ordinary least squares. Investigation established the cause. "
      "One feature on that dataset has a standard deviation near 66,000 while the remaining "
      "fifteen are below 0.34, giving the centred matrix a condition number of 1.4 times ten "
      "to the seventh. The least-squares solver discards singular values below a tolerance "
      "defined relative to the largest, so on the unscaled data it fitted using 9 of the 16 "
      "available directions and reported no error. Refitting the raw data with a tighter "
      "tolerance restored all sixteen directions and reproduced the scaled result exactly. The "
      "estimator is scale invariant, and what changed was the number of features the solver "
      "retained. The practical implication is that on data with one dominant-scale feature, "
      "omitting scaling can silently reduce a linear model to a subset of its features."),
("h3", "4.4.2 Encoding"),
("p", "Encoding produced no significant global test in any of its cells. That outcome is "
      "reported here as a failure to test the question rather than as evidence that the "
      "choice of encoder does not matter, and the distinction is worth making precisely."),
("p", "A cell is a no-op when all three encoders return exactly the same score, which happens "
      "whenever a dataset has no categorical features for them to act on. Counting those "
      "cells directly: 54 of the 64 classification cells and 20 of the 32 regression cells "
      "are no-ops. Only three of the sixteen classification datasets carry any categorical "
      "features at all, and three of the eight regression datasets. The comparison was "
      "therefore conducted largely on data where the treatment cannot have an effect, and "
      "the resulting null carries no information about encoders."),
("p", "This also explains an otherwise odd observation. Five datasets added late in the study "
      "left the encoding test statistics unchanged to four decimal places, because all five "
      "are entirely numeric and all twenty of their new cells returned identical scores "
      "across the three encoders. The arm therefore remains at eleven effective datasets "
      "while the scaling, selection and tuning arms stand at sixteen."),
("p", "Where categorical features are present the picture differs, although the sample is too "
      "small to test. On the two large categorical datasets, ordinal encoding cost logistic "
      "regression 8.2 macro F1 points on adult and 7.1 on bank-marketing relative to one-hot "
      "encoding, while the tree ensembles moved only slightly and the support vector machine "
      "did not move at all. The direction is consistent with ordinal encoding imposing an "
      "arbitrary numeric order on unordered categories, which a linear model treats as "
      "meaningful."),
("h3", "4.4.3 Imputation"),
("p", "The imputation arm produced 23 of the 34 surviving contrasts and also required the most "
      "careful reading, because the same data support different conclusions depending on which "
      "technique is taken as the reference."),
("p", "Compared against mean imputation, nearest-neighbour imputation was significantly better "
      "in nine cells, concentrated at the 15 and 30 per cent missing rates under both "
      "mechanisms, typically improving on 7 or 8 of the 9 datasets. Median imputation was "
      "significantly worse than mean imputation for regression, rejected in five of the six "
      "sweeps and worse on all nine datasets in three of them, which is the most "
      "directionally consistent result in the study. Gradient boosting showed no response to "
      "the imputer in any sweep. Figure 4.4 summarises where the nearest-neighbour advantage "
      "appears."),
("fig", ("fig3_imputation_knn_vs_mean.png",
         "Figure 4.4: Cells in which nearest-neighbour imputation was significantly better "
         "than mean imputation after correction, by missingness mechanism and rate.")),
("p", "Compared against row deletion, the Chapter 1 baseline, the same sweeps produced a "
      "larger number of contrasts, and on classification these indicated that imputing "
      "outperforms deleting. On regression the comparison appeared to show the opposite, with "
      "row deletion beating every imputer on eight or nine of the nine datasets. That apparent "
      "result does not survive examination and is addressed in section 4.5.2."),
("p", "A further analysis compared the imputers with one another on the uninjected data and "
      "found no significant difference anywhere, with every p-value above 0.09. The reason is "
      "not that imputer choice is immaterial but that the comparison had almost nothing to "
      "test: twenty of the twenty-six datasets contain no missing values at all, and only one "
      "has a rate comparable to the injected sweeps. The null is therefore reported as a "
      "statement about the registry rather than about the imputers."),
("p", "Set against the earlier B2 findings, the present results agree at the 15 per cent rate "
      "under both mechanisms and at 30 per cent under the completely-at-random mechanism. They "
      "do not reproduce the 5 per cent result, where nearest-neighbour imputation leads on "
      "seven of nine datasets without reaching significance, and they add a marginal advantage "
      "at 30 per cent under the at-random mechanism that B2 did not report. This is partial "
      "agreement obtained from a different registry and a different set of models, and is "
      "described as such."),
("h3", "4.4.4 Feature selection"),
("p", "The feature-selection arm produced the clearest instance in the study of a result that "
      "the design initially could not detect, and of what changed once the design was "
      "corrected."),
("p", "On its first analysis the arm returned five significant global tests and no surviving "
      "pairwise contrast. That combination is easily mistaken for a null result, and it is "
      "not one. A two-sided Wilcoxon signed-rank test on n paired datasets has a smallest "
      "attainable p-value of 2 divided by 2 to the power n, and the Holm procedure multiplies "
      "the smallest of k comparisons by k. Table 4.4 gives the floor for the combinations "
      "relevant to this study."),
("tbl", ("Table 4.4: Smallest attainable corrected p-value by number of datasets and "
         "comparisons.",
         [["Datasets (n)", "Comparisons (k)", "Smallest attainable Holm p", "Can reject at 0.05"],
          ["7", "3", "0.0469", "Yes, marginally"],
          ["7", "4", "0.0625", "No"],
          ["8", "4", "0.0312", "Yes"],
          ["9", "4", "0.0156", "Yes"],
          ["11", "4", "0.0039", "Yes"]])),
("p", "At seven regression datasets with four comparisons the procedure cannot return a value "
      "below 0.0625, which is above the threshold. No contrast in those cells could have been "
      "rejected whatever the size of the real effect, and three of the strongest global "
      "signals in the study, at p-values of 0.0009, 0.0010 and 0.0021, fell into exactly that "
      "position. The limitation follows from the power considerations raised by García et al. "
      "(2010), and it was identified after the data had been collected rather than during "
      "the design, which Chapter 5 returns to."),
("p", "Because the shortfall was a single dataset, it could be addressed rather than only "
      "reported. An eighth regression dataset was added to the registry and the affected arms "
      "were re-run, which lowered the floor to 0.0312 and made the cells testable. The "
      "re-analysis confirmed that the blocked signals were real. Chi-square filtering and "
      "recursive elimination both significantly worsened gradient boosting on regression "
      "data, each at a corrected p-value of 0.0312, with chi-square worse on 8 of the 8 "
      "datasets and recursive elimination worse on 8 of 8. The global test for that cell "
      "stood at 0.0053, so the effect had been present and undetectable rather than absent."),
("p", "The direction of that finding deserves emphasis because it runs against the usual "
      "framing of feature selection as a neutral or mildly beneficial step. On regression "
      "data in this registry, applying a univariate filter to gradient boosting made the "
      "model worse on every dataset tested."),
("p", "The magnitudes support the same reading. The median spread across selection techniques "
      "was below 4 per cent of the baseline score, but on the energy-efficiency dataset the "
      "chi-square and mutual-information filters raised gradient boosting error from 0.467 to "
      "3.08, an increase of more than sixfold, by discarding features the model required in "
      "combination. Recursive elimination, which evaluates features jointly rather than "
      "individually, stayed within 4 per cent of no selection on that dataset even though it "
      "was significantly worse across the arm as a whole. Figure 4.5 shows the distribution."),
("fig", ("fig9_selection_tail_risk.png",
         "Figure 4.5: The most selection-sensitive combinations of dataset and model. The "
         "median effect is small and the tail is large.")),

("h3", "4.4.5 Hyperparameter tuning"),
("p", "Tuning consumed 58.1 of the 85.5 measured hours, or 68 per cent of the total compute. "
      "On the first analysis it produced one surviving contrast. After the eighth regression "
      "dataset was added, as described in section 4.4.4, it produced three. Grid search "
      "improved the support vector regressor at a corrected p-value of 0.0234, better on 8 "
      "of 8 datasets, which is a stronger result than the 0.0469 obtained at seven datasets. "
      "Grid and Bayesian search each improved gradient boosting on regression at 0.0469, "
      "better on 7 of 8 datasets, neither of which could have been detected before. Random "
      "search was not rejected for any model."),
("p", "On the three large datasets, examined in a separate sweep, gradient boosting was the "
      "only model that tuning moved consistently, gaining between 1.4 and 1.9 macro F1 points "
      "on the classification datasets and reducing error by between 4.5 and 7.3 per cent on "
      "the regression dataset. Logistic regression and random forest moved slightly or not at "
      "all. Grid, random and Bayesian search were indistinguishable from one another on every "
      "model and dataset. Figure 4.6 shows the comparison."),
("fig", ("fig5_tuning_cost_benefit.png",
         "Figure 4.6: Improvement over no tuning on the three large datasets. The right panel "
         "reports percentage error reduction and the other two report macro F1 points, so bar "
         "heights are not comparable between panels.")),
("p", "The cost measured here bears on the practical question posed in the research question. "
      "A single grid-search fit of random forest on the adult dataset took 1,379 seconds, and "
      "the equivalent random search took 1,259 seconds, which is why the large-dataset tuning "
      "sweep alone consumed 31.2 hours for 36 runs. Set against a single surviving contrast "
      "across the whole programme, tuning is the component with the least favourable ratio of "
      "evidence to compute in this study."),
("p", "Because wall time, processor time and peak memory are recorded on every run, the "
      "cost of each component can be characterised rather than only totalled. Table 4.5 "
      "gives the mean cost of a run by component and dataset size."),
("tbl", ("Table 4.5: Mean wall-clock seconds per run, by component and dataset size, with "
         "the ratio between the smallest and largest size band.",
         [["Component", "Under 1,000 rows", "1,000 to 10,000", "Over 10,000", "Ratio"],
          ["Encoding", "2.6", "14.5", "133.2", "51x"],
          ["Scaling", "2.4", "6.1", "244.1", "101x"],
          ["Feature selection", "2.9", "14.8", "642.7", "224x"],
          ["Hyperparameter tuning", "54.1", "483.8", "3,404.4", "63x"]])),
("p", "Two points follow. Tuning is the most expensive component at every size, starting an "
      "order of magnitude above the others on small data, which is the cost behind the 68 "
      "per cent share reported above. Feature selection, by contrast, is inexpensive on "
      "small data and scales worst of the four, rising 224-fold across the size bands, "
      "because the wrapper methods refit a model once per candidate subset."),
("p", "Cost also varies by model independently of the component. Averaged across every "
      "recorded run, gradient boosting took 118.5 seconds and random forest 104.5, against "
      "29.8 for the support vector machine and 26.8 for logistic regression. Set beside the "
      "finding that tuning reliably helps only gradient boosting, this means the component "
      "with the least favourable evidence-to-cost ratio is also the one whose benefit is "
      "confined to the most expensive model family."),

("h3", "4.4.6 Dependence on the evaluation protocol"),
("p", "The secondary protocol was applied to establish whether the results are an artefact of "
      "the way the data were split. Across sixteen combinations of dataset, model and scaling "
      "technique measured under both protocols, the two agreed in direction and in magnitude, "
      "as Figure 4.7 shows."),
("fig", ("fig6_protocol_agreement.png",
         "Figure 4.7: Accuracy measured under ten-fold cross-validation against accuracy "
         "measured under thirty repeated holdout splits. Points on the diagonal indicate "
         "agreement.")),
("p", "The house_16H result described in section 4.4.1 reappeared under the secondary "
      "protocol with the same signature: min-max, standard and robust scaling produced "
      "identical error of 45,829.3 against 49,445.8 without scaling. Obtaining the same "
      "pattern under a different splitting scheme supports the explanation given there, since "
      "a property of the data and the solver should not depend on how the data are partitioned."),

("h3", "4.4.7 Dependence on the random seed"),
("p", "Every run described so far used seed 671. Because the seed determines the fold "
      "assignment, a result reported as holding on 10 of 11 datasets could in principle be a "
      "property of that one assignment rather than of the data. The scaling arm was therefore "
      "repeated in full under two further seeds, 1337 and 20260702, giving three independent "
      "estimates of the same quantity. The seeds are not pooled: pooling would treble the "
      "apparent sample while the datasets stayed the same."),
("tbl", ("Table 4.6: The scaling result for logistic regression under three random seeds.",
         [["Seed", "Friedman p", "Standard vs none, Holm", "Datasets improved",
           "Median difference"],
          ["671", "0.0275", "0.0410, rejected", "10 of 11", "+0.0061"],
          ["1337", "0.0742", "not licensed", "8 of 11", "+0.0080"],
          ["20260702", "0.1746", "not licensed", "8 of 11", "+0.0070"]])),
("p", "The result is mixed and is reported as such. The contrast reaches significance under "
      "one seed of the three, so the claim that standard scaling significantly improves "
      "logistic regression does not survive replication in the form originally stated. What "
      "does survive is the effect itself. Standard scaling is better than no scaling on the "
      "majority of datasets under every seed, and the median improvement is close to constant "
      "at 0.61, 0.80 and 0.70 of a percentage point. The direction and the size are stable; "
      "what moves is whether the win count clears the threshold the test applies."),
("p", "The explanation is the one set out in section 4.4.4. At eleven datasets the Wilcoxon "
      "procedure is sensitive to a small number of sign changes, so a result sitting at 10 of "
      "11 under one fold assignment and 8 of 11 under another crosses the significance "
      "boundary even though the underlying difference has barely moved. This is a limitation "
      "of the available sample rather than evidence that the effect is absent."),
("p", "One further observation emerged from the replication, and it was later confirmed by "
      "a different route. Under seed 1337 the support vector machine produced three rejected "
      "contrasts on accuracy where the other two seeds returned Friedman values of 0.0530 and "
      "0.0771, both close to the threshold. At the time this looked like the same "
      "intermittency affecting logistic regression. When five further datasets were added and "
      "the arm was re-tested at sixteen, the support vector machine result became significant "
      "under the original seed as well, at a corrected 0.0071 with an interval excluding zero. "
      "The instability was a symptom of the sample size, and enlarging the sample resolved it "
      "in the direction the replication had already indicated."),
("p", "The replication supports a more useful statement than a simple pass or fail. If "
      "instability were random, disagreement between seeds would fall evenly across "
      "datasets. It does not. Across the 132 combinations of model, scaler and dataset "
      "measured under all three seeds, agreement on the direction of the effect depends "
      "strongly on how large that effect is."),
("tbl", ("Table 4.7: Agreement between three random seeds on the direction of the scaling "
         "effect, by the size of that effect. Cells where all three seeds return exactly "
         "zero are excluded as true no-ops rather than counted as disagreement.",
         [["Mean effect size", "Cells", "Seeds agree on direction", "Rate"],
          ["Below 1 percentage point", "51", "15", "29 per cent"],
          ["1 percentage point or more", "42", "39", "93 per cent"]])),
("p", "A Fisher exact test on that table returns an odds ratio of 31.2 at p below 0.0001. "
      "An effect of at least one percentage point reproduces its direction across "
      "independent fold assignments in 93 per cent of cases; an effect below that threshold "
      "does so in 29 per cent. The exclusion of true no-ops makes this the conservative "
      "reading, since including them raises the odds ratio to 65."),
("p", "This gives the study a practical rule rather than only a caveat. At eleven datasets "
      "and ten-fold cross-validation, a scaling difference below roughly one percentage "
      "point should not be trusted from a single random seed, and a difference above it "
      "generally can be. The rule is specific to this registry and protocol, but the "
      "procedure that produced it transfers: a researcher can establish the equivalent "
      "threshold for their own setting by repeating one arm under two further seeds, which "
      "cost 1.8 hours here."),

("p", "The scaling arm was chosen for replication because it carried the headline result. The "
      "imputation arm carries more of them, 23 of the 34 surviving contrasts, and all of them "
      "rested on the same single seed. Leaving the largest arm untested while reporting a "
      "replication of a smaller one would not have been defensible, so all six injected sweeps "
      "were repeated under seed 1337, a further 1,728 runs at a measured cost of 2.6 hours. "
      "The seed changes both the fold assignment and the injected missingness pattern, which "
      "is the stronger test: it asks whether a finding survives a different draw rather than a "
      "different split of the same gaps."),
("p", "The outcome is considerably worse than for scaling and is reported in full."),
("tbl", ("Table 4.8: Imputation contrasts under two random seeds, across all six injected "
         "sweeps. A contrast counts as reproduced when it survives Holm correction under both.",
         [["Outcome", "Contrasts"],
          ["Rejected under seed 671 and reproduced under 1337", "8"],
          ["Rejected under seed 671 but not under 1337", "15"],
          ["Rejected under 1337 but not under 671", "9"],
          ["Reproduction rate of the original findings", "8 of 23, 35 per cent"]])),
("p", "Agreement on the global test is 50 of 72 cells, or 69 per cent, so the two seeds "
      "disagree about whether an effect exists at all in 22 cells. Several of those "
      "disagreements are not marginal. The clearest is random forest accuracy at 30 per cent "
      "missingness under the missing-at-random mechanism, which returns a Friedman p-value of "
      "0.0063 under one seed and 0.9718 under the other."),
("p", "That case was examined directly rather than accepted from the test output. Both seeds "
      "use the same nine datasets and produce comparable scores, so the registry is identical "
      "and the comparison is sound. Under the first seed, nearest-neighbour imputation beats "
      "mean imputation on eight of nine datasets with one tie; under the second it wins on "
      "four of nine. Only one dataset, digits, holds both the direction and the size of its "
      "difference. On every other dataset the difference is under one percentage point, and at "
      "that missingness rate its sign is determined by which cells the injector happened to "
      "remove. The comparison is not crossing a threshold, it is returning opposite answers "
      "because the quantity being measured is smaller than the noise in measuring it."),
("p", "The effect-size rule established above was tested on this arm as an independent check, "
      "over 843 comparisons measured under both seeds."),
("tbl", ("Table 4.9: Agreement between two random seeds on the direction of the imputation "
         "effect, by the size of that effect, with the scaling figures repeated for comparison.",
         [["Mean effect size", "Imputation, 2 seeds", "Scaling, 3 seeds"],
          ["Below 1 percentage point", "205 of 368, 56 per cent", "15 of 51, 29 per cent"],
          ["1 percentage point or more", "371 of 475, 78 per cent", "39 of 42, 93 per cent"]])),
("p", "A Fisher exact test returns an odds ratio of 2.8 at p below 0.0001, so the rule holds "
      "in direction on an arm it was not derived from, which is genuine support for it. The "
      "levels are another matter. Agreement above the threshold is 78 per cent here against 93 "
      "for scaling, and below it 56 per cent, which is close to what guessing would produce. "
      "Raising the threshold does not repair this: agreement reaches 84 per cent at two "
      "percentage points and then settles near 85, never approaching the scaling figure. There "
      "is no effect size at which an imputation result on nine datasets becomes as dependable "
      "as a scaling result on sixteen, because the limitation is the sample rather than the "
      "effect."),
("p", "Three consequences follow for how this study reports its imputation results. They are "
      "presented with the reproduction rate attached rather than as settled findings. The "
      "eight contrasts that did reproduce are identified as the defensible subset, and they "
      "are coherent: nearest-neighbour imputation beating mean imputation on regression holds "
      "across both seeds at several missingness rates, and median imputation being worse than "
      "mean on regression holds at zero or one of nine datasets under both. The remaining "
      "conclusions are provisional, with the nine-dataset sample named as the binding "
      "constraint."),
("p", "The wider point is methodological. A study that reports 34 significant contrasts and "
      "one that reports 34 contrasts of which the largest arm reproduces at 35 per cent are "
      "making very different claims, and only the second can be checked. The replication cost "
      "4.4 hours against the programme's 85.5, which is a small price for knowing which of "
      "the results would survive someone else running them. Section 4.4.8 goes further and "
      "tests the explanation offered for the shortfall, rather than leaving it as a "
      "plausible account."),

("p", "The comparison above uses two seeds, which can only report whether a pair of draws "
      "agreed. A third draw was therefore added, seed 20260702, matching the three-seed design "
      "already used for scaling and run on the same nine datasets so the result is comparable "
      "with the figures above. That permits a better question than agreement: of three "
      "independent draws, how many reject each contrast?"),
("tbl", ("Table 4.10: Every imputation contrast ever rejected, by how many of three random "
         "seeds rejected it. Nine datasets, identical design in each draw.",
         [["Rejected under", "Contrasts", "Share"],
          ["All three seeds", "3", "8 per cent"],
          ["Two of three seeds", "9", "25 per cent"],
          ["One seed only", "24", "67 per cent"],
          ["Total ever rejected", "36", ""]])),
("p", "Two thirds of everything this arm has ever called significant appears under exactly one "
      "draw of three. Each of those 24 contrasts would have been reported as a finding had "
      "that seed been the only one run, which is how a single-seed study is ordinarily "
      "conducted. Only three contrasts survive all three draws: median imputation being worse "
      "than mean for regression at 5 per cent missingness, under both mechanisms, and "
      "nearest-neighbour imputation beating mean for the support vector machine at 30 per cent "
      "missing completely at random. The most dependable result the arm produces is a negative "
      "one."),
("p", "The three draws are not equally generous, and the difference is material. Under an "
      "identical design, seed 671 rejects 23 contrasts, seed 1337 rejects 17, and seed "
      "20260702 rejects 11. The run counts per sweep are identical and the success counts "
      "nearly so, which was checked before the comparison was trusted, so this reflects the "
      "draws themselves rather than any asymmetry in how they were executed."),
("p", "Seed 671 is the seed this study's findings rest on, and it is the most generous of the "
      "three by a factor of two. That is not a case of selecting a favourable result: the seed "
      "was fixed before any data was collected and is recorded throughout, as the "
      "pre-registration required. The point is the opposite and more uncomfortable. An "
      "honestly pre-committed but arbitrary choice still determined more than half of what "
      "this arm reported, and no amount of care in choosing it could have helped, because "
      "there is no principled basis on which to choose a random seed. The only remedy is to "
      "run more than one."),

("h3", "4.4.8 Testing the diagnosis: a larger registry"),
("p", "Section 4.4.7 attributed the imputation arm's 35 per cent reproduction rate to its "
      "nine-dataset sample rather than to any deeper instability. That is an explanation, and "
      "an explanation of this kind can be tested by changing the thing it names. Seven further "
      "registry entries qualified for the arm and had not been used in it: five complete "
      "numeric classification datasets and two regression datasets. Adding them takes the arm "
      "to fourteen classification and eleven regression datasets. All six injected sweeps were "
      "then run again under both seeds, 4,822 runs over roughly 24 hours."),
("tbl", ("Table 4.11: The imputation arm at two registry sizes, compared over the same 72 "
         "statistical cells. Only the number of datasets differs; the seeds, protocol, "
         "techniques and models are identical.",
         [["", "Nine datasets", "Fourteen and eleven datasets"],
          ["Contrasts reproduced under both seeds", "8 of 23", "10 of 17"],
          ["Reproduction rate", "35 per cent", "59 per cent"],
          ["Agreement on the global test", "50 of 72, 69 per cent",
           "54 of 72, 75 per cent"]])),
("p", "Reproduction rose from 35 to 59 per cent and agreement on the global test from 69 to "
      "75. The rate was measured five times as the sweeps completed, at 57, 60, 62 and 59 per "
      "cent on successively larger samples, so it is a stable figure rather than a single "
      "favourable reading. The diagnosis in section 4.4.7 is therefore supported by "
      "intervention rather than by argument: the variable it named was changed, and the "
      "quantity it predicted would move did move, in the predicted direction."),
("p", "This changes what the pair of results means. Taken alone, section 4.4.7 is a "
      "limitation, namely that most of the main arm's findings do not replicate. Taken with "
      "this section it becomes a measured relationship between the size of a dataset registry "
      "and the reproducibility of the findings drawn from it, established by manipulating one "
      "and observing the other. That is the strongest methodological result in the study."),
("p", "It also fixes the honest ceiling. Fifty-nine per cent is better than 35 but it is not "
      "high: at fourteen datasets, four of every ten rejected contrasts still fail to survive "
      "a change of random seed. The recommendation that follows is not that the problem is "
      "solved, but that studies of this kind need larger registries than the field "
      "conventionally uses, and that the shortfall can be measured rather than assumed."),

("h3", "4.4.9 A pre-registered test on data the study had never seen"),
("p", "Every result reported so far was produced on a registry that grew while the study ran, "
      "and datasets were added in response to what earlier results showed. That is documented "
      "and defensible for exploratory work, but it means no finding so far is a clean "
      "confirmation, because the data that generated a hypothesis cannot also test it. One "
      "test was therefore pre-registered to close that gap."),
("p", "The prediction, the datasets, the procedure and the decision rule were written down and "
      "committed to the project's version control before any of the datasets had been scored, "
      "so the record establishes that the hypothesis preceded the data. The prediction was "
      "that standard scaling improves support vector machine accuracy relative to no scaling, "
      "the study's best-supported result, on five complete numeric classification datasets "
      "never previously used. The registered bar was a one-sided Wilcoxon p-value below 0.05 "
      "and at least four of five datasets improved. Random forest was included as a control, "
      "on the expectation that it would show nothing."),
("tbl", ("Table 4.12: The pre-registered held-out test. Standard scaling against no scaling, "
         "support vector machine accuracy, on five datasets the study had never used.",
         [["Dataset", "No scaling", "Standard scaling", "Difference"],
          ["eeg-eye-state", "0.5512", "0.6587", "+0.1075"],
          ["kc1", "0.8502", "0.8530", "+0.0028"],
          ["mozilla4", "0.8720", "0.8736", "+0.0015"],
          ["diabetes_sylva", "0.7136", "0.7119", "-0.0017"],
          ["wall-robot-nav", "0.8906", "0.8886", "-0.0020"]])),
("p", "The prediction was not confirmed. Standard scaling improved three of the five datasets "
      "at a one-sided p-value of 0.3125, against a registered bar of 0.05 and four of five. "
      "The registered falsification condition, two or fewer improvements, was also not met, so "
      "the registered verdict is a failure to confirm rather than a refutation. The control "
      "behaved as intended: random forest improved on one of five at a p-value of 0.6875 with "
      "a median difference of -0.0001, so the procedure is not one that finds an effect "
      "wherever it looks."),
("p", "The pattern within the result is more informative than the verdict. One dataset moved "
      "by 10.8 percentage points, the largest single scaling effect recorded anywhere in this "
      "study, and the remaining four moved by less than 0.3 of a percentage point in either "
      "direction. Those four sit inside the band where section 4.4.7 established that the sign "
      "of a difference does not reproduce. The effect appeared where it was large and was "
      "absent where it was small, which is consistent with the effect-size threshold the study "
      "derived independently, but it is not what was registered and cannot be claimed as a "
      "confirmation."),
("p", "A negative result on the study's own instrumentation belongs here too. A "
      "feature-scale-disparity statistic was added to the run record to close the gap "
      "identified in section 4.6, and it separates the pathological house_16H case from "
      "ordinary datasets by five orders of magnitude. It does not predict these scaling gains: "
      "the dataset that moved most has the second lowest value of the five. The statistic "
      "measures what it was built to measure, a least-squares solver discarding feature "
      "directions, and support vector machine kernel sensitivity is a different mechanism. "
      "Closing one instrumentation gap did not close the other."),

("p", "Reporting a replication that partly fails is more useful than omitting it. The honest "
      "statement the study can make is that scaling benefits the two scale-sensitive models "
      "in direction and magnitude across independent fold assignments, and that the dataset "
      "registry is not large enough for that benefit to reach significance reliably."),

("h2", "4.5 Trustworthiness of the results"),
("p", "Section 2.2 set out four measures through which rigour was pursued. This section "
      "reports how each was applied in practice, including two occasions on which the "
      "instrument exposed a defect in its own output."),
("h3", "4.5.1 Demonstrating the absence of leakage"),
("p", "The structural guarantee described in section 4.1.1 was verified rather than assumed. A "
      "wrapper records the identity and count of the rows each transformer receives at every "
      "fit, and six tests assert that no transformer was fitted on data outside its training "
      "fold. The tests include the nested case, asserting that the inner tuning search never "
      "sees the outer test fold and that each inner fit is strictly smaller than the outer "
      "training partition. A deliberately leaky pipeline is constructed alongside the correct "
      "one, and the suite fails if the instrumentation does not detect it, so the tests cannot "
      "pass vacuously."),
("p", "The size of what the guarantee prevents can be measured directly. Fitting the scaler "
      "and the feature selector on the complete dataset before splitting, which is the error "
      "Kaufman et al. (2012) describe, and then evaluating under the same ten-fold protocol, "
      "produces a higher score than the correct pipeline on the same data and the same seed. "
      "The inflation arises because the selector has already seen the targets of the rows it "
      "is later scored on. Nothing in the output of the leaky pipeline indicates that this "
      "has happened: it raises no error, produces no warning and returns a result of the "
      "expected shape. That is the reason the study treats the absence of leakage as "
      "something to be demonstrated for each run rather than inferred from the structure of "
      "the code."),
("h3", "4.5.2 A comparison that measured the wrong quantity"),
("p", "The regression result described in section 4.4.3, in which row deletion appeared to "
      "outperform every imputer, was examined before being reported. Row deletion is not "
      "scored on the same data as the imputers: it removes every row containing a missing "
      "value and is then evaluated on what remains. On the bodyfat dataset at a 15 per cent "
      "missing rate it retained 38 of 252 rows and recorded an error of 0.21 against mean "
      "imputation at 2.90 on the full data. Figure 4.8 shows the relationship across the arm."),
("fig", ("fig4_droprows_artefact.png",
         "Figure 4.8: Error ratio of row deletion to mean imputation against the proportion of "
         "rows retained. The fewer rows retained, the more favourable the comparison appears.")),
("p", "Every point lies below parity, and the advantage grows as the retained sample shrinks. "
      "The comparison measures the difficulty of the remaining sample rather than the quality "
      "of the imputation, and the regression direction is therefore withdrawn. The "
      "classification comparison is retained but described as a comparison of two workflows "
      "rather than a like-for-like comparison on identical test data."),
("h3", "4.5.3 A significant result produced by a defect"),
("p", "An earlier tuning sweep reported that Bayesian search improved support vector machine "
      "macro F1 relative to no tuning, with a p-value of 0.0145. At the time this was the "
      "second strongest result in the programme. Examination of the run record showed that "
      "random search and grid search had produced identical scores on all 56 combinations of "
      "model and dataset, which should not occur if the two search strategies differ."),
("p", "The cause was a search budget larger than the search space. Each hyperparameter grid "
      "contained between four and six candidates while random search was configured to draw "
      "ten, so random search exhausted the grid and became grid search, and Bayesian search "
      "drew its trials from the same small set of points. After the random and Bayesian "
      "strategies were given continuous ranges to search at the same budget, the sweep was "
      "repeated under a new configuration name so that the two sets of results would not be "
      "pooled. The same comparison then returned a p-value of 0.2330, and the advantage "
      "reversed on two datasets. The original result was withdrawn. It had measured how "
      "closely a Bayesian search reproduces a small fixed grid rather than how well it tunes "
      "a model."),
("h3", "4.5.4 Integrity of the record"),
("p", "The run record was treated as append-only throughout. Before each commit of the "
      "database the file was checked for structural integrity and queried for duplicate "
      "successful cells. On two occasions a defect was found after a sweep had begun writing "
      "rows; because the database had not yet been committed, the affected rows were discarded "
      "and the sweep was repeated from the start rather than leaving known-defective rows in a "
      "record that does not permit deletion. Both occasions are documented in the project log."),
("p", "The software itself was tested continuously, with 342 tests covering the engine and 303 "
      "covering the interface. The tests include the leakage proofs described in section "
      "4.5.1, verification that the missingness injector matches the earlier implementation, "
      "and an assertion that the statistical output shown in the interface matches the engine."),

("h2", "4.6 Findings"),
("p", "The results reported above support the following findings, stated at the level of "
      "confidence the evidence allows."),
("p", "Five findings rest on contrasts that survived correction, though the first is "
      "qualified by the replication in section 4.4.7. Standard scaling improves "
      "logistic regression relative to no scaling under the study seed, with the same "
      "direction and effect size but without significance under two further seeds. Grid "
      "search improves the support vector "
      "regressor relative to no tuning. Nearest-neighbour imputation outperforms mean "
      "imputation at injected missing rates of 15 and 30 per cent, depending on the model. "
      "Median imputation performs worse than mean imputation for linear regression under "
      "injected missingness. Imputing outperforms deleting rows for gradient boosting on "
      "classification data."),
("p", "Table 4.13 gives the effect size behind each of the five tested findings, since a "
      "corrected p-value on its own states that a difference exists without stating how large "
      "it is or how firmly its direction is established."),
("tbl", ("Table 4.13: Effect sizes for the tested findings, with bootstrapped 95 per cent "
         "confidence intervals on the median paired difference.",
         [["Finding", "Holm p", "Median difference", "95% CI", "Improved"],
          ["Standard scaling over none, logistic regression (accuracy)",
           "0.0410", "+0.0061", "+0.0015 to +0.0228", "10 of 11"],
          ["Grid search over none, support vector regressor (RMSE)",
           "0.0469", "+1.1845", "+0.1878 to +3.8219", "7 of 7"],
          ["kNN over mean, logistic regression, 15% MCAR (RMSE)",
           "0.0078", "+0.2891", "+0.0292 to +0.9276", "8 of 9"],
          ["Median below mean, logistic regression, 15% MCAR (RMSE)",
           "0.0078", "-0.0598", "-0.1339 to -0.0003", "0 of 9"],
          ["kNN over mean, random forest, 30% MAR (accuracy)",
           "0.0156", "+0.0085", "+0.0018 to +0.0317", "8 of 9"]])),
("p", "The intervals qualify the results in a way the p-values do not. Of the 29 contrasts "
      "that survived correction across the programme, 14 have an interval that excludes zero "
      "and 11 have one that touches or crosses it. The second group lies almost entirely in "
      "the imputation arm, where several nearest-neighbour advantages have a lower bound at "
      "or just below zero despite a corrected p-value under 0.05. Those contrasts are "
      "reported as rejected because the procedure rejects them, but the direction of the "
      "difference is less firmly settled than the p-value alone would suggest, and they "
      "carry less weight than the five in Table 4.13."),
("p", "The magnitudes are modest. The scaling result moves median accuracy by about 0.6 of a "
      "percentage point and the classification imputation results by between 0.3 and 3 "
      "percentage points. For the regression contrasts the differences are expressed in the "
      "units of each target, which are not comparable between datasets, so the direction and "
      "the number of datasets improved carry more weight than the size of the median "
      "difference."),

("p", "Four further observations are supported by direct measurement but not by a statistical "
      "test, because the sweeps concerned covered too few datasets. The support vector machine "
      "gains more than twenty macro F1 points from standard scaling on the two large "
      "classification datasets. Gradient boosting is the only model that tuning reliably "
      "improves on large datasets. Ordinal encoding costs logistic regression between seven "
      "and eight macro F1 points on the two large categorical datasets. L1-based selection "
      "retains 5 of 104 features on adult but 49 of 51 on bank-marketing, which is the "
      "sharpest instance of a single technique behaving differently on different data."),
("p", "Three null results are reported with the same weight. Encoding produced no detectable "
      "effect in any tested cell. Tree ensembles showed no response to scaling, and gradient "
      "boosting showed none to the choice of imputer. No search strategy outperformed any "
      "other."),
("p", "Two results were withdrawn, as described in sections 4.5.2 and 4.5.3, and one apparent "
      "null was shown in section 4.4.4 to be a limit of the test rather than a property of the "
      "data."),
("p", "This chapter has described the artefact, the cycles through which it was developed, the "
      "experiments conducted and the results obtained, including the measures that establish "
      "their trustworthiness and the two occasions on which the instrument corrected its own "
      "output. Chapter 5 evaluates the study against the objectives stated in Chapter 1 and "
      "reflects on the process followed."),
("pg", ""),

# ===================== CHAPTER 5 ===================================
("h1", "Chapter 5: Conclusion"),
("p", "The focus of this project was to measure how far five preprocessing decisions affect "
      "tabular model performance, and to build an instrument capable of producing that "
      "measurement credibly. This chapter closes the study by assessing what was achieved "
      "against what was intended."),
("p", "The chapter summarises the research process, states the contributions the study makes, "
      "discusses the limitations that bound those contributions and the future work they "
      "suggest, evaluates the trustworthiness of the study against the measures set out in "
      "Chapter 2, and reflects on the decisions taken and the management of the project."),
("p", "The sections that follow move from a summary of the work, through its contributions "
      "and limitations, to an evaluation and a reflection."),

("h2", "5.1 Overview of the research"),
("p", "The study began from the observation that preprocessing decisions are made before "
      "every tabular model is trained, and that controlled evidence about which of them change "
      "the outcome is harder to find than the frequency of the decisions would suggest. Three "
      "difficulties were identified as obstacles to producing such evidence: leakage, which "
      "inflates results invisibly; confounding, which prevents attribution; and incomplete "
      "recording, which prevents a result from being audited later."),
("p", "The response was to build an instrument that addresses all three, and then to use it. "
      "Pipeline Lab composes preprocessing techniques into pipelines in which every "
      "transformation is fitted inside the cross-validation fold, varies one component at a "
      "time against a declared baseline, and appends each run to a record of 89 typed columns "
      "covering performance, data characteristics, resource use and software environment. The "
      "system was applied across 23 sweeps, producing 4,761 experimental runs over 31 datasets "
      "and four model families at a measured cost of 85.5 hours. A further 7,449 runs over 29.0 "
      "hours were spent replicating and extending two of those arms, and 20 on a "
      "pre-registered confirmation, bringing the record to 12,210 runs."),
("p", "The analysis followed the procedure recommended by Demšar (2006), testing 167 cells and "
      "finding 34 contrasts that survived correction for multiple comparisons. The pattern of "
      "those results, rather than any single one of them, answers the research question: most "
      "preprocessing choices produced no detectable difference, and the differences that did "
      "appear belong to particular model families rather than to pipelines in general."),
("p", "The five objectives stated in section 1.2.4 were met. The engine was built and its "
      "leakage safety demonstrated through instrumentation rather than assertion. The "
      "one-factor-at-a-time design was implemented across five components and four models. The "
      "statistical framework was applied as pre-committed, including in the cases where it "
      "declined to license a pairwise claim. Cost was measured alongside every result, which "
      "produced the finding about tuning reported in section 4.4.5. The dependence of the "
      "results on the evaluation protocol was tested and found to be absent across the "
      "combinations examined."),

("h2", "5.2 Contributions of the research"),
("p", "The study makes contributions of three kinds, which are described in turn."),
("h3", "5.2.1 The artefact"),
("p", "The principal contribution is Pipeline Lab itself: an experimentation system that "
      "measures single-factor preprocessing effects with demonstrated leakage safety, full "
      "provenance and recorded cost. The system is not specific to the questions asked here. "
      "Adding a preprocessing technique requires a factory function and its tests, after which "
      "the technique inherits the leakage guarantee, the provenance capture and the "
      "statistical treatment. The same applies to model families and to datasets."),
("p", "The run record is a contribution in its own right. Because cost and data "
      "characteristics are stored beside every score, questions that were not anticipated "
      "during collection can be answered afterwards without repeating the work. This was "
      "demonstrated within the study: a later analysis of the same 4,441 rows established that "
      "the proportion of categorical features in a dataset predicts how much the encoding "
      "choice matters, with a Spearman correlation of 0.88, and showed that an apparently "
      "strong second predictor disappeared once that proportion was controlled for."),
("h3", "5.2.2 Empirical contributions"),
("p", "The study contributes controlled measurements of five preprocessing components under "
      "identical conditions, which the literature reviewed in Chapter 3 does not provide. The "
      "specific findings are listed in section 4.6. Their common theme is that preprocessing "
      "effects are conditional on the model family, which refines the general advice found in "
      "applied texts into something that can be acted on for a particular model."),
("p", "The measurement of cost alongside effect is a further empirical contribution. The "
      "finding that hyperparameter tuning consumed 68 per cent of the compute while producing "
      "one surviving contrast is not available from studies that report accuracy alone, and it "
      "bears directly on how a practitioner with a fixed compute budget should allocate it."),
("h3", "5.2.3 Methodological contributions"),
("p", "Three methodological contributions arise from occasions when the instrument corrected "
      "its own output. The withdrawal of the Bayesian tuning result demonstrates a failure "
      "mode worth naming: a search budget that exceeds the search space degenerates into "
      "exhaustive search while continuing to produce plausible numbers. The withdrawal of the "
      "regression imputation result demonstrates that a baseline evaluated on a different "
      "sample is not a baseline, and that the error is detectable only if sample sizes are "
      "recorded per run."),
("p", "The third concerns statistical power. The discovery that five significant global tests "
      "could not possibly have produced a surviving pairwise contrast, because the smallest "
      "attainable corrected p-value exceeded the threshold, is a concrete instance of a "
      "limitation that follows from the procedure recommended by Demšar (2006) and analysed by "
      "García et al. (2010). Stating it in the form given in Table 4.4 may help other "
      "researchers check their design before collecting data rather than after."),

("h2", "5.3 Limitations and future research"),
("p", "The limitations of the study bound what its findings support, and several of them point "
      "directly at work that would extend it."),
("h3", "5.3.1 Limitations"),
("p", "The one-factor-at-a-time design cannot detect interactions between components. Every "
      "result reported here holds the other four components at their baselines, so a technique "
      "that helps only in combination with another would not appear. This is the most "
      "significant limitation of the study and it is a property of the design rather than of "
      "its execution."),
("p", "Several arms rest on too few datasets to support a statistical test. The large-dataset "
      "sweeps covered one or two datasets each, so the results in sections 4.4.1, 4.4.2 and "
      "4.4.5 relating to those sweeps are direct readings rather than tested findings, and are "
      "described as such throughout. The feature-selection regression arm was subject to the "
      "power limit described in section 4.4.4."),
("p", "The registry contains almost no natural missing values, with 26 of its 31 datasets "
      "having none. The uninjected imputation arm therefore tests very little, and "
      "the controlled injection used for the remaining analysis, while necessary, produces "
      "missingness patterns that are more regular than those found in collected data."),
("p", "Effect sizes are not comparable across datasets whose targets are on different scales, "
      "so for regression the direction of a difference and the count of datasets on which it "
      "holds are more reliable than the magnitude of the median difference. Timings are "
      "specific to the single machine recorded with them. The datasets are predominantly "
      "small and clean, which is not representative of data encountered in practice."),
("p", "The replication reported in section 4.4.7 exposed a limitation more serious than "
      "the single-seed design it was intended to test. Repeating the scaling arm under two "
      "further seeds left the direction and the size of the effect unchanged but moved the "
      "contrast across the significance threshold, so the arm reaches significance under "
      "one seed of three. At eleven datasets the test is sensitive to a small number of "
      "sign changes, which means the registry is not large enough to establish this "
      "finding reliably rather than that the finding is absent. The same applies to the "
      "support vector machine arm, significant under a different single seed. Any claim "
      "in this study that rests on a win count near the threshold should be read with "
      "that instability in mind."),
("h3", "5.3.2 Future research"),
("p", "The most direct extension is to interaction effects. The engine supports arbitrary "
      "combinations of techniques already, and only the design contract restricts it to one "
      "varied factor, so a factorial or fractional factorial study would require a "
      "configuration change rather than new development. Scaling and feature selection are the "
      "pair most likely to interact, since both alter the geometry of the feature space."),
("p", "A second line follows from the record rather than from new experiments. The analysis "
      "described in section 5.2.1 examined only a few dataset properties; a fuller treatment "
      "could ask which measurable characteristics predict that a given preprocessing choice "
      "will matter, using the 4,441 rows already collected. One instrumentation change would "
      "assist this work: the record does not currently store a measure of feature-scale "
      "disparity, which the house_16H result in section 4.4.1 suggests would be informative."),
("p", "Three further directions are worth noting. Extending the injector to the missing not at "
      "random mechanism would complete the taxonomy described by Little and Rubin (2019). "
      "Replicating the study on an independent registry would test the model-specificity claim "
      "more severely than anything attempted here, since every finding is conditioned on these "
      "31 datasets. Finally, support vector machine tuning on the large datasets was the one "
      "combination left unmeasured, because its cost was never established."),

("h2", "5.4 Evaluation of the study"),
("p", "Chapter 2 set out four measures through which rigour was pursued, and Chapter 4 "
      "reported how each was applied. This section assesses whether they were sufficient."),
("p", "Attribution was enforced structurally rather than by convention, since the "
      "configuration loader refuses a configuration that pins the component being varied. Any "
      "difference reported here can therefore be attributed to the component named, within the "
      "limits of the design. The absence of leakage was demonstrated by instrumentation that "
      "records what each transformer was fitted on, and the demonstration is non-vacuous "
      "because a deliberately leaky pipeline is tested alongside the correct one and must "
      "fail."),
("p", "Reliability rests on a fixed seed, a protocol selected on the basis of Kohavi (1995), "
      "and a secondary protocol that reproduced the primary results across the combinations "
      "examined. The statistical treatment followed Demšar (2006) as pre-committed, and the "
      "implementation declines to report a pairwise comparison that the global test does not "
      "license, which removed the possibility of over-reporting at the point where it is "
      "easiest to do."),
("p", "The strongest evidence for the trustworthiness of the study is that the instrument "
      "detected two defects in its own output. A result that was significant at p equals "
      "0.0145 was withdrawn after the record showed that two search strategies had produced "
      "identical scores on all 56 combinations, and a second result was withdrawn after the "
      "recorded sample sizes showed that a baseline had been evaluated on a reduced sample. "
      "Neither would have been visible in a record that stored scores alone. The study is "
      "presented as auditable rather than as free of error, and these two cases are the "
      "evidence for that claim."),

("h2", "5.5 Reflection on the study"),
("p", "This section reflects on what was learnt, on whether the objectives were met and on how "
      "the project was managed."),
("h3", "5.5.1 Decisions taken and lessons drawn"),
("p", "The decision that shaped the study most was to build the recording system before "
      "running experiments rather than adding it afterwards. It delayed the first results by "
      "several weeks and appeared at the time to be effort diverted from the research "
      "question. Both withdrawn results and the dataset-characteristic analysis depended on "
      "information that would not have existed had the record been added later, so the "
      "decision is judged correct in hindsight."),
("p", "A second decision, to measure the cost of an expensive operation before committing to "
      "it, was adopted after an early estimate proved unreliable. Measuring a single fit and "
      "extrapolating from it replaced qualitative guesses with numbers and made it possible to "
      "decide which sweeps were affordable. The practice was applied consistently after that "
      "point."),
("p", "The clearest lesson concerns the order in which power should be considered. The "
      "feature-selection limitation described in section 4.4.4 was discovered after the data "
      "had been collected, when it could no longer be addressed. Computing the smallest "
      "attainable corrected p-value for the intended design takes minutes and would have "
      "indicated that the regression arm needed more datasets before any run was executed. "
      "This is the single change that would most improve a repeat of the study."),
("p", "A further lesson concerns the interpretation of an unexpected observation. On two "
      "occasions a result that looked like a finding turned out, on investigation, to be a "
      "property of the measurement rather than of the data. In both cases the investigation "
      "was prompted by the result appearing implausible rather than by any automatic check, "
      "which suggests that plausibility remains a necessary part of the process even when the "
      "statistical procedure has been followed correctly."),
("h3", "5.5.2 Achievement of objectives"),
("p", "The five objectives were met, as set out in section 5.1. The achievement is qualified "
      "in one respect: the objective of establishing which effects are supportable was met for "
      "the components where the registry provided sufficient datasets, and was not fully met "
      "for feature selection on regression data, where the design could not have produced a "
      "significant result. That shortfall is reported rather than presented as a null finding, "
      "which is the appropriate treatment given what the analysis showed."),
("h3", "5.5.3 Project management"),
("p", "The project ran from February to October and was managed in stages, each ending with a "
      "working system and a sweep whose results informed the next stage. This arrangement "
      "proved valuable when defects appeared, since the two withdrawn results were each found "
      "at the end of a stage and corrected before the following one began, rather than "
      "accumulating until the end."),
("p", "Scheduling was less successful than sequencing. The compute cost of the tuning arm was "
      "underestimated at the outset, and the final large-dataset tuning sweep required "
      "approximately 30 hours of continuous execution, which constrained the time available "
      "for the later analysis. A repeat of the project would measure the cost of the most "
      "expensive arm during planning rather than shortly before running it. The practice of "
      "recording progress and decisions in a project log as the work proceeded made the "
      "reconstruction of events for this report straightforward, and is a habit worth keeping."),

("p", "Figure 5.1 sets the windows in the module's assessment plan against dated evidence "
      "of the work: the chapter drafts, the histories of the three artefact repositories, the "
      "ethics documents and the run record. Two departures from the plan are visible. Ethics "
      "clearance was finalised at the end of August rather than by the end of March, although "
      "it preceded every experimental run. The artefact on which the final results rest was "
      "built in October, after the two earlier iterations described in section 4.2, which "
      "compressed the experimentation into the final weeks before submission."),
("fig", ("fig10_project_timeline.png",
         "Figure 5.1: Planned assessment windows against dated evidence of the work. Light bars "
         "show the windows in the module's assessment plan; dark bars show the dates carried by "
         "the chapter files, repository histories, ethics documents and run record.")),
("h2", "5.6 Closing summary"),
("p", "This study set out to determine how far five preprocessing decisions affect the "
      "performance of models on tabular data, and what each costs to apply. It answered that "
      "question by building an instrument designed so that its results could be trusted, and "
      "by applying that instrument across 4,761 controlled runs, and a further 7,469 spent "
      "testing whether its own results reproduce and why."),
("p", "The answer is largely negative and is useful for that reason. Most preprocessing "
      "choices produced no detectable effect, and the effects that exist are specific to "
      "particular model families rather than general properties of pipelines. Hyperparameter "
      "tuning, the most expensive component by a wide margin, yielded a single supportable "
      "contrast. The encoding comparison is reported as untested rather than null, because "
      "the registry contains too few categorical datasets for the encoders to differ."),
("p", "The replications qualify these conclusions and are the reason to trust what remains. Repeating the scaling and imputation arms under further seeds showed that the imputation findings reproduce at 35 per cent while the scaling effect holds in direction and magnitude throughout, and in both arms reproducibility tracked effect size. Enlarging the imputation registry then raised reproduction to 59 per cent, which turns that shortfall from an unexplained weakness into a measured relationship between registry size and reproducibility. Set against this, a pre-registered test of the strongest result on five unseen datasets did not confirm it. The study can therefore say which of its results would survive another researcher running them, and on what the answer depends, which is more useful than a longer list of significant contrasts would have been."),
("p", "The methodological outcome carries comparable weight. The system withdrew one of its "
      "own significant results after exposing the defect that produced it, quantified a "
      "measurement artefact that would otherwise have supported misleading advice, and "
      "identified a case in which no result could have been confirmed at the sample sizes "
      "used. These outcomes were available because the instrument recorded more than the "
      "scores, which supports the position taken throughout this report: the credibility of a "
      "preprocessing comparison is bounded by the instrument that produces it."),
("pg", ""),

("refs", None),
("pg", None),
("h1", "Appendix A: Research ethics form"),
("p", "The ITRI 671 research ethics form was completed by the researcher and signed by the "
      "researcher and the study leader, Prof I. Smit, on 31 August 2026. The signed form is "
      "attached to the submission as a separate document, Appendix A - Research ethics form "
      "(signed).pdf. Table A.1 records its answers."),
("tbl", ("Table A.1: Answers recorded on the signed research ethics form.",
         [["Question on the form", "Answer"],
          ["Read the prescribed material on research ethics", "Yes"],
          ["People used as a source of data", "No"],
          ["Permission needed from another party", "No"],
          ["Foreseeable risk to participants or the environment", "No"],
          ["Foreseeable risk to the NWU", "No"],
          ["Other ethical issues, including conflicts of interest", "No"]])),
("pg", None),
("h1", "Appendix B: Research ethics training and code of conduct"),
("p", "The researcher completed three modules of the TRREE training programme in research ethics "
      "evaluation and signed the NWU Code of Conduct for Researchers. Each certificate and the "
      "signed code are attached as separate documents."),
("tbl", ("Table B.1: Research ethics training certificates and the signed code of conduct.",
         [["Document", "Title", "Date", "Reference"],
          ["TRREE Module 1", "Introduction to Research Ethics", "30 August 2026", "VV1PXTjMTE"],
          ["TRREE Module 2", "Research Ethics Evaluation", "30 August 2026", "lbwlotWW55"],
          ["TRREE Module 3", "Informed Consent", "30 August 2026", "WLnQfaaG4C"],
          ["NWU Code of Conduct for Researchers", "Signed by the researcher", "31 August 2026",
           "9.1.5.1.3"]])),
("pg", None),
("h1", "Appendix C: Pre-registration of the held-out test"),
("p", "The prediction tested in section 4.4.9 was written down and committed to the project's "
      "version control before any of the five held-out datasets had been scored. The commit "
      "record establishes the order of events independently of this report."),
("tbl", ("Table C.1: The pre-registration record and the terms it fixed in advance.",
         [["Item", "Recorded value"],
          ["Commit", "1f82653"],
          ["Committed", "18 October 2026, 04:54:31 UTC"],
          ["First held-out run", "18 October 2026, 04:55:26 UTC"],
          ["Prediction", "Standard scaling improves support vector machine accuracy relative "
                         "to no scaling on five unseen datasets"],
          ["Pass condition", "One-sided Wilcoxon p below 0.05 and at least four of five "
                             "datasets improved"],
          ["Falsification condition", "Direction reversed, or two or fewer datasets improved"],
          ["Control", "Random forest, expected to show no effect"],
          ["Outcome", "Three of five improved, p = 0.3125: not confirmed (section 4.4.9)"]])),
("pg", None),
("h1", "Appendix D: Reproduction materials"),
("p", "The submission package contains the complete run record, the analysis scripts that "
      "produce every figure and table in Chapter 4, and the source of the experimentation engine "
      "archived at the version used for the final results. A notebook, main_colab.ipynb, "
      "re-executes the experiments in a fresh environment with the same pinned library versions "
      "and compares the new record with the original cell by cell, so that the results can be "
      "checked by someone other than the researcher."),
("tbl", ("Table D.1: Reproduction materials in the submission package.",
         [["Material", "Purpose"],
          ["Run record (lab.db)", "Every run with its scores, data characteristics, cost and "
                                  "software environment"],
          ["Analysis scripts", "Regenerate the figures and statistical results reported in "
                               "Chapter 4"],
          ["Engine archive", "Source of the experimentation engine at the final version"],
          ["main_colab.ipynb", "Re-runs the experiments and compares the new record with the "
                               "original"]])),
]

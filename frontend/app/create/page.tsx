'use client';

import Link from "next/link";
import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";

export default function CreatePage() {
  const { getWalletAddress, isAuthenticated } = useAuth();
  const searchParams = useSearchParams();
  const reviseTokenId = searchParams.get('revise');

  const [currentSection, setCurrentSection] = useState(1);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const [revising, setRevising] = useState<string | null>(reviseTokenId);
  const [revisionNotes, setRevisionNotes] = useState('');
  const [originalModelName, setOriginalModelName] = useState<string>('');

  const [createMode, setCreateMode] = useState<'new' | 'version'>('new');
  const [existingModels, setExistingModels] = useState<any[]>([]);
  const [selectedParentModel, setSelectedParentModel] = useState<string>('');

  const [useExample, setUseExample] = useState(false);

  const [sectionErrors, setSectionErrors] = useState<{[key: number]: string[]}>({});
  const [sectionSaved, setSectionSaved] = useState<{[key: number]: boolean}>({});
  const [savingSection, setSavingSection] = useState<number | null>(null);

  const [ohdsiLoading, setOhdsiLoading] = useState(false);
  const [ohdsiError, setOhdsiError] = useState('');
  const [cdmSources, setCdmSources] = useState<any[]>([]);
  const [cohortDetails, setCohortDetails] = useState<any>(null);
  const [fetchingCohort, setFetchingCohort] = useState(false);

  const [creatingCohort, setCreatingCohort] = useState(false);
  const [newCohortName, setNewCohortName] = useState('');
  const [newCohortDescription, setNewCohortDescription] = useState('');
  const [cohortCriteria, setCohortCriteria] = useState({
    primaryConditionConceptId: '',
    primaryConditionName: '',
    ageMin: '',
    ageMax: '',
    genderConceptId: '',
    observationPeriodDays: '365'
  });

  const [heraclesData, setHeraclesData] = useState<any>(null);
  const [fetchingHeracles, setFetchingHeracles] = useState(false);

  const [formData, setFormData] = useState({
    modelName: "",
    version: "1.0.0",
    developerOrg: "",
    releaseDate: "",
    description: "",
    clinicalFunction: "decision_support",
    intendedPurpose: "decision_support",
    algorithmsUsed: "",
    licensing: "MIT",
    gmdnCode: "",
    supportContact: "",
    literatureRefs: "",
    informationSignificance: "",
    basicUdiDi: "",
    udiDi: "",
    regulatoryClassifications: "",
    clinicalStudyReferences: "",
    logoImage: "",

    primaryUsers: "",
    clinicalIndications: "",
    patientTargetGroup: "",
    useEnvironment: "hospital_outpatient",
    contraindications: "",
    outOfScope: "",
    warnings: "",

    datasetName: "",
    datasetOrigin: "",
    datasetSize: "",
    collectionPeriod: "",
    populationChars: "",
    dataDistribution: "",
    dataRepresentativeness: "",
    dataGovernance: "",
    useOMOP: false,
    omopIntegrationMethod: "manual",
    omopWebApiUrl: "https://atlas-demo.ohdsi.org/WebAPI",
    omopConceptSetIds: "",
    omopConceptSetNames: "",
    omopCohortId: "",
    omopCohortName: "",
    omopCohortSize: "",
    omopCohortStatus: "",
    omopSelectedSource: "",
    omopIncludeHeracles: true,
    demographicsAge: "",
    demographicsGender: "",
    demographicsEthnicity: "",
    demographicsOther: "",

    inputFeatures: "",
    outputFeatures: "",
    featureTypeDistribution: "",
    uncertaintyQuantification: "",
    outputInterpretability: "",

    validationDatasets: "",
    claimedMetrics: "",
    validatedMetrics: "",
    metricValidationStatus: "claimed",
    calibrationAnalysis: "",
    fairnessAssessment: "",
    developmentWorkflow: "",
    trainingProcedure: "",
    dataPreprocessing: "",
    syntheticDataUsage: "",
    explainableAI: "",
    globalVsLocalInterpretability: "",

    benefitRiskSummary: "",
    ethicalConsiderations: "",
    caveatsLimitations: "",
    recommendationsSafeUse: "",
    postMarketSurveillancePlan: "",
    explainabilityRecommendations: "",
    supportingDocuments: "",

    lineName: "",
    relation: 0,
    supersedes: 0,
    withinEnvelope: false,
    envelopeText: "",
    parentLineLookup: "",
  });

  const COPD_EXAMPLE = {
    modelName: "COPD Exacerbation Risk Predictor",
    version: "1.0.0",
    developerOrg: "Clinical AI Research Group",
    releaseDate: new Date().toISOString().split('T')[0],
    description: "Logistic regression model that estimates the 12-month risk of moderate-to-severe acute exacerbation in adults with chronic obstructive pulmonary disease (COPD), using routinely collected EHR features mapped to the OMOP Common Data Model.",
    clinicalFunction: "decision_support",
    intendedPurpose: "decision_support",
    algorithmsUsed: "Logistic regression with L2 regularization on OMOP-derived features",
    licensing: "MIT",
    gmdnCode: "",
    supportContact: "smart@example.org",
    literatureRefs: "Lohachab et al. SMART: Structured, Meaningful, Auditable, Responsible, and Transparent documentation for clinical AI (under review).",
    informationSignificance: "drive",
    basicUdiDi: "",
    udiDi: "",
    regulatoryClassifications: "EU MDR | Class IIa | Rule 11 | CE-marked\nFDA | SaMD II | clinical decision support | 510(k)",
    clinicalStudyReferences: "ClinicalTrials.gov NCT00000000 (illustrative)",
    logoImage: "",

    primaryUsers: "Pulmonologists, primary-care clinicians, care managers",
    clinicalIndications: "Risk stratification for acute exacerbation in adults with confirmed COPD diagnosis",
    patientTargetGroup: "Adults aged 40+ with a confirmed COPD diagnosis (OMOP concept 255573 and descendants) and at least 12 months of observation history",
    useEnvironment: "hospital_outpatient",
    contraindications: "Patients without a confirmed COPD diagnosis; pediatric patients; insufficient EHR history",
    outOfScope: "Diagnosis of COPD; differential diagnosis from asthma; severity grading",
    warnings: "Output is a risk estimate, not a diagnosis. Clinicians must integrate the score with clinical judgement before any care decision.",

    datasetName: "Institutional OMOP CDM extract",
    datasetOrigin: "De-identified EHR data harmonized to the OMOP CDM v5.4",
    datasetSize: "12,438",
    collectionPeriod: "2018-01-01 to 2023-12-31",
    populationChars: "Adults with a confirmed COPD diagnosis at the index date and at least 12 months of prior observation",
    dataDistribution: "Train: 70%, Validation: 15%, Held-out test: 15%; stratified by exacerbation outcome",
    dataRepresentativeness: "Single-network cohort; external generalizability requires further validation",
    dataGovernance: "Institutional IRB-approved secondary use; data remains within the operator's environment",
    useOMOP: true,
    omopIntegrationMethod: "webapi",
    omopWebApiUrl: "https://atlas-demo.ohdsi.org/WebAPI",
    omopConceptSetIds: "",
    omopConceptSetNames: "COPD (255573 and descendants)",
    omopCohortId: "",
    omopCohortName: "Adults with COPD, 12+ months observation",
    omopCohortSize: "",
    omopCohortStatus: "",
    omopSelectedSource: "",
    omopIncludeHeracles: true,
    demographicsAge: "Mean: 67.4 years, Range: 40-94 years",
    demographicsGender: "Male: 54%, Female: 46%",
    demographicsEthnicity: "Per OMOP race/ethnicity concepts; reported in Heracles characterization",
    demographicsOther: "Active smoker: 31%, former smoker: 52%, never smoker: 17%",

    inputFeatures: "Age, sex, prior exacerbation count (12 months), GOLD stage, FEV1% predicted, comorbidities (heart failure, diabetes, anxiety), inhaled-therapy classes. All derived via OMOP concept sets.",
    outputFeatures: "Calibrated probability of one or more moderate-to-severe exacerbations within 12 months",
    featureTypeDistribution: "12 features (5 numeric, 7 categorical); single scalar probability output",
    uncertaintyQuantification: "Bootstrapped 95% confidence interval reported per prediction",
    outputInterpretability: "Per-prediction feature contributions via standardized logistic-regression coefficients",

    validationDatasets: "Internal held-out test set (n=1,866); temporal validation on 2024 records (n=2,103)",
    claimedMetrics: "AUROC: 0.78 (95% CI 0.76-0.80), AUPRC: 0.42, Brier score: 0.14, ECE: 0.03",
    validatedMetrics: "Pending independent authenticator validation",
    metricValidationStatus: "claimed",
    calibrationAnalysis: "Reliability diagram with 10 deciles; isotonic recalibration applied",
    fairnessAssessment: "Subgroup AUROC reported across age bands, sex, and smoking status; no clinically significant disparities at the chosen operating threshold",

    developmentWorkflow: "1) Cohort definition via OMOP concept sets, 2) Feature extraction from condition/drug/measurement domains, 3) Train/val/test split, 4) L2-regularized logistic regression with hyperparameter tuning, 5) Internal + temporal validation, 6) Calibration and fairness analysis",
    trainingProcedure: "L2-regularized logistic regression; 5-fold CV on the training set; class-imbalance handling via inverse-frequency weighting",
    dataPreprocessing: "Median imputation for missing numeric features, one-hot encoding for categorical features, standardization of numeric features prior to fitting",
    syntheticDataUsage: "No synthetic data used in training or validation.",
    explainableAI: "Per-feature standardized coefficients; per-prediction contribution decomposition",
    globalVsLocalInterpretability: "Global: standardized coefficients summarize feature directionality and magnitude across the cohort. Local: per-prediction contribution breakdown supports clinician reasoning at the patient level.",

    benefitRiskSummary: "Benefits: identifies high-risk patients for proactive outreach. Risks: over-reliance on the score, potential automation bias, dataset shift in new sites.",
    ethicalConsiderations: "Trained on de-identified retrospective data; downstream interventions should be evaluated for equity across subgroups before deployment.",
    caveatsLimitations: "1) Single-network training data, 2) Requires OMOP-mapped EHR, 3) Not validated outside the development health system, 4) Performance may drift with care-pathway changes.",
    recommendationsSafeUse: "1) Use as a population-management aid, not for individual care decisions in isolation; 2) Re-evaluate calibration quarterly; 3) Trigger revalidation if site-level prevalence of exacerbation shifts by more than 10%.",
    postMarketSurveillancePlan: "Quarterly review of calibration and subgroup AUROC against new admissions; revalidation triggered when prevalence shifts by more than 10% or AUROC degrades below 0.72.",
    explainabilityRecommendations: "Pair the score with the per-prediction contribution breakdown when discussing risk with clinicians; do not surface the score in isolation.",
    supportingDocuments: "https://example.org/copd-validation-report.pdf\nhttps://example.org/copd-fairness-supplement.pdf",

    lineName: "copd-exacerbation-risk",
    relation: 0,
    supersedes: 0,
    withinEnvelope: true,
    envelopeText: "Quarterly retrains on data from clinical sites within the original deployment region. Performance bounds: AUROC >= 0.75 on the holdout, calibration slope within [0.9, 1.1]. No changes to input feature set, output threshold, or deployment indication.",
    parentLineLookup: "",
  };

  const populateWithExample = () => {
    setFormData(prev => ({
      ...prev,
      ...COPD_EXAMPLE
    }));
    setUseExample(true);
  };

  const clearExample = () => {
    setFormData({
      modelName: "",
      version: "1.0.0",
      developerOrg: "",
      releaseDate: "",
      description: "",
      clinicalFunction: "decision_support",
      intendedPurpose: "decision_support",
      algorithmsUsed: "",
      licensing: "MIT",
      gmdnCode: "",
      supportContact: "",
      literatureRefs: "",
      informationSignificance: "",
      basicUdiDi: "",
      udiDi: "",
      regulatoryClassifications: "",
      clinicalStudyReferences: "",
      logoImage: "",
      primaryUsers: "",
      clinicalIndications: "",
      patientTargetGroup: "",
      useEnvironment: "hospital_outpatient",
      contraindications: "",
      outOfScope: "",
      warnings: "",
      datasetName: "",
      datasetOrigin: "",
      datasetSize: "",
      collectionPeriod: "",
      populationChars: "",
      dataDistribution: "",
      dataRepresentativeness: "",
      dataGovernance: "",
      useOMOP: false,
      omopIntegrationMethod: "manual",
      omopWebApiUrl: "https://atlas-demo.ohdsi.org/WebAPI",
      omopConceptSetIds: "",
      omopConceptSetNames: "",
      omopCohortId: "",
      omopCohortName: "",
      omopCohortSize: "",
      omopCohortStatus: "",
      omopSelectedSource: "",
      omopIncludeHeracles: true,
      demographicsAge: "",
      demographicsGender: "",
      demographicsEthnicity: "",
      demographicsOther: "",
      inputFeatures: "",
      outputFeatures: "",
      featureTypeDistribution: "",
      uncertaintyQuantification: "",
      outputInterpretability: "",
      validationDatasets: "",
      claimedMetrics: "",
      validatedMetrics: "",
      metricValidationStatus: "claimed",
      calibrationAnalysis: "",
      fairnessAssessment: "",
      developmentWorkflow: "",
      trainingProcedure: "",
      dataPreprocessing: "",
      syntheticDataUsage: "",
      explainableAI: "",
      globalVsLocalInterpretability: "",
      benefitRiskSummary: "",
      ethicalConsiderations: "",
      caveatsLimitations: "",
      recommendationsSafeUse: "",
      postMarketSurveillancePlan: "",
      explainabilityRecommendations: "",
      supportingDocuments: "",
      lineName: "",
      relation: 0,
      supersedes: 0,
      withinEnvelope: false,
      envelopeText: "",
      parentLineLookup: "",
    });
    setUseExample(false);
  };

  useEffect(() => {
    if (createMode === 'version') {
      fetchExistingModels();
    }
  }, [createMode]);

  // Section keys must match what track_model_card_in_neo4j reads.
  const buildMetadataPayload = (fd: typeof formData) => ({
    "1. Model Details": {
      "Model Name": fd.modelName,
      "Version": fd.version,
      "Developer / Organization": fd.developerOrg,
      "Release Date": fd.releaseDate || new Date().toISOString().split('T')[0],
      "Description": fd.description,
      "Clinical Function": fd.clinicalFunction,
      "Intended Purpose": fd.intendedPurpose,
      "Algorithm(s) Used": fd.algorithmsUsed,
      "Licensing": fd.licensing || "Not specified",
      "Support Contact": fd.supportContact,
      "GMDN Code": fd.gmdnCode,
    },
    "2. Intended Use and Clinical Context": {
      "Primary Intended Users": fd.primaryUsers,
      "Clinical Indications": fd.clinicalIndications,
      "Patient target group": fd.patientTargetGroup,
      "Intended Use Environment": fd.useEnvironment,
      "Contraindications": fd.contraindications,
      "Out of Scope Applications": fd.outOfScope,
      "Warnings": fd.warnings,
    },
    "3. Data & Factors": {
      "Data Distribution Summary": fd.dataDistribution,
      "Data Representativeness": fd.dataRepresentativeness,
      "Data Governance": fd.dataGovernance,
    },
    "4. Features & Outputs": {
      "Feature Type Distribution": fd.featureTypeDistribution,
      "Uncertainty Quantification": fd.uncertaintyQuantification,
      "Output Interpretability": fd.outputInterpretability,
    },
    "5. Performance & Validation": {
      "Metric Validation Status": fd.metricValidationStatus,
      "Calibration Analysis": fd.calibrationAnalysis,
      "Fairness Assessment": fd.fairnessAssessment,
    },
    "6. Methodology & Explainability": {
      "Model Development Workflow": fd.developmentWorkflow,
      "Training Procedure": fd.trainingProcedure,
      "Data Preprocessing": fd.dataPreprocessing,
      "Synthetic Data Usage": fd.syntheticDataUsage,
      "Explainable AI Method": fd.explainableAI,
      "Global vs Local Interpretability": fd.globalVsLocalInterpretability,
    },
    "7. Additional Information": {
      "Benefit–Risk Summary": fd.benefitRiskSummary,
      "Ethical Considerations": fd.ethicalConsiderations,
      "Caveats & Limitations": fd.caveatsLimitations,
      "Recommendations for Safe Use": fd.recommendationsSafeUse,
      "Post-Market Surveillance Plan": fd.postMarketSurveillancePlan,
      "Explainability Recommendations": fd.explainabilityRecommendations,
    },
  });

  // Revise mode: load the existing card and prefill the form. Metadata key
  // paths must match what the smart-model-card library produces.
  useEffect(() => {
    if (!revising) return;
    const wallet = getWalletAddress();
    const url = wallet
      ? `http://localhost:8000/api/model-cards/${revising}?actor=${encodeURIComponent(wallet)}`
      : `http://localhost:8000/api/model-cards/${revising}`;
    (async () => {
      try {
        const r = await fetch(url);
        if (!r.ok) {
          const d = await r.json().catch(() => ({}));
          toast.error(d.detail || 'Could not load card to revise');
          setRevising(null);
          return;
        }
        const card = await r.json();
        const md = card.metadata || {};
        const m1 = md["1. Model Details"] || {};
        const m2 = md["2. Intended Use and Clinical Context"] || md["2. Intended Use"] || {};
        const m3 = md["3. Data & Factors"] || md["3. Data Factors"] || {};
        const m4 = md["4. Features & Outputs"] || {};
        const m5 = md["5. Performance & Validation"] || {};
        const m6 = md["6. Methodology & Explainability"] || md["6. Methodology"] || {};
        const m7 = md["7. Additional Information"] || {};

        const name = m1["Model Name"] || card.model_name || '';
        setOriginalModelName(name);

        const linesFrom = (arr: any) =>
          Array.isArray(arr) ? arr.map((x) => (typeof x === 'string' ? x : JSON.stringify(x))).join('\n') : '';
        const featuresLines = (arr: any) =>
          Array.isArray(arr)
            ? arr
                .map((f: any) =>
                  [f.name, f.data_type || f.type, f.required ? 'required' : 'optional', f.clinical_domain || ''].filter(Boolean).join(' | ')
                )
                .join('\n')
            : '';
        const metricsLines = (arr: any) =>
          Array.isArray(arr)
            ? arr.map((m: any) => [m.metric_name, m.value, m.subgroup || ''].filter((x) => x !== undefined).join(' | ')).join('\n')
            : '';
        const datasetsLines = (arr: any) =>
          Array.isArray(arr)
            ? arr.map((d: any) => [d.name, d.source_institution || d.institution || '', d.validation_type || ''].filter(Boolean).join(' | ')).join('\n')
            : '';
        const sourceDataset0 = Array.isArray(m3["Source Datasets"]) ? m3["Source Datasets"][0] || {} : {};
        const regClsLines = (arr: any) =>
          Array.isArray(arr)
            ? arr.map((r: any) => [r.framework, r.class, r.rule || '', r.pathway || ''].filter(Boolean).join(' | ')).join('\n')
            : '';

        setFormData((prev) => ({
          ...prev,
          modelName: name,
          version: m1["Version"] || card.version || prev.version,
          developerOrg: m1["Developer / Organization"] || card.developer_organization || '',
          releaseDate: m1["Release Date"] || prev.releaseDate,
          description: m1["Description"] || card.description || '',
          clinicalFunction: m1["Clinical Function"] || prev.clinicalFunction,
          intendedPurpose: m1["Intended Purpose"] || '',
          algorithmsUsed: m1["Algorithm(s) Used"] || '',
          licensing: m1["Licensing"] || '',
          gmdnCode: m1["GMDN Code"] || '',
          supportContact: m1["Support Contact"] || '',
          literatureRefs: linesFrom(m1["Literature References"]),
          informationSignificance: m1["Information Significance"] || '',
          basicUdiDi: m1["Basic UDI-DI"] || '',
          udiDi: m1["UDI-DI"] || '',
          regulatoryClassifications: regClsLines(m1["Regulatory Classifications"]),
          clinicalStudyReferences: linesFrom(m1["Clinical Study References"]),
          primaryUsers: m2["Primary Intended Users"] || '',
          clinicalIndications: m2["Clinical Indications"] || '',
          patientTargetGroup: m2["Patient target group"] || m2["Patient Target Group"] || '',
          useEnvironment: m2["Intended Use Environment"] || prev.useEnvironment,
          contraindications: m2["Contraindications"] || '',
          outOfScope: m2["Out of Scope Applications"] || '',
          warnings: m2["Warnings"] || '',
          datasetName: sourceDataset0.name || '',
          datasetOrigin: sourceDataset0.origin || '',
          datasetSize: sourceDataset0.size != null ? String(sourceDataset0.size) : '',
          collectionPeriod: sourceDataset0.collection_period || '',
          populationChars: sourceDataset0.population_characteristics || '',
          dataDistribution: m3["Data Distribution Summary"] || '',
          dataRepresentativeness: m3["Data Representativeness"] || '',
          dataGovernance: m3["Data Governance"] || '',
          demographicsAge: sourceDataset0?.demographics?.age || '',
          demographicsGender: sourceDataset0?.demographics?.gender || '',
          demographicsEthnicity: sourceDataset0?.demographics?.ethnicity || '',
          demographicsOther: sourceDataset0?.demographics?.other || '',
          inputFeatures: featuresLines(m4["Input Features"]),
          outputFeatures: featuresLines(m4["Output Features"]),
          featureTypeDistribution: m4["Feature Type Distribution"] || '',
          uncertaintyQuantification: m4["Uncertainty Quantification"] || '',
          outputInterpretability: m4["Output Interpretability"] || '',
          validationDatasets: datasetsLines(m5["Validation Dataset(s)"]),
          claimedMetrics: metricsLines(m5["Claimed Metrics"]),
          validatedMetrics: metricsLines(m5["Validated Metrics"]),
          metricValidationStatus: m5["Metric Validation Status"] || prev.metricValidationStatus,
          calibrationAnalysis: m5["Calibration Analysis"] || '',
          fairnessAssessment: m5["Fairness Assessment"] || '',
          developmentWorkflow: m6["Model Development Workflow"] || '',
          trainingProcedure: m6["Training Procedure"] || '',
          dataPreprocessing: m6["Data Preprocessing"] || '',
          syntheticDataUsage: m6["Synthetic Data Usage"] || '',
          explainableAI: m6["Explainable AI Method"] || '',
          globalVsLocalInterpretability: m6["Global vs Local Interpretability"] || '',
          benefitRiskSummary: m7["Benefit–Risk Summary"] || m7["Benefit-Risk Summary"] || '',
          ethicalConsiderations: m7["Ethical Considerations"] || '',
          caveatsLimitations: m7["Caveats & Limitations"] || m7["Caveats and Limitations"] || '',
          recommendationsSafeUse: m7["Recommendations for Safe Use"] || '',
          postMarketSurveillancePlan: m7["Post-Market Surveillance Plan"] || '',
          explainabilityRecommendations: m7["Explainability Recommendations"] || '',
          supportingDocuments: linesFrom(m7["Supporting Documents"]),
        }));
      } catch {
        toast.error('Failed to load card');
        setRevising(null);
      }
    })();
  }, [revising]);  // eslint-disable-line react-hooks/exhaustive-deps

  const fetchExistingModels = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/model-cards?status=Deprecated');
      const data = await response.json();
      const uniqueModels = new Map();

      data.model_cards?.forEach((item: any) => {
        const mc = item.mc || item;
        if (mc.model_name && mc.current_status === 'Deprecated' && !mc.superseded_by) {
          const key = `${mc.developer_organization}_${mc.model_name}`;
          if (!uniqueModels.has(key)) {
            uniqueModels.set(key, {
              model_name: mc.model_name,
              token_id: mc.token_id,
              version: mc.version || '1.0.0',
              developer_organization: mc.developer_organization
            });
          }
        }
      });

      setExistingModels(Array.from(uniqueModels.values()));
    } catch (error) {
      console.error('Error fetching existing models:', error);
    }
  };

  const handleInputChange = (field: string, value: string | boolean) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const validateSection = (sectionNumber: number): string[] => {
    const errors: string[] = [];

    switch (sectionNumber) {
      case 1:
        if (createMode === 'version') {
          if (existingModels.length === 0) {
            errors.push("No archived models available. You must archive a published model first before creating a new version.");
          } else if (!selectedParentModel) {
            errors.push("Please select an archived model to supersede");
          }
        } else {
          if (!formData.modelName.trim()) errors.push("Model Name is required");
        }
        if (createMode === 'new' && !formData.version.trim()) errors.push("Version is required");
        if (!formData.developerOrg.trim()) errors.push("Developer/Organization is required");
        if (!formData.description.trim()) errors.push("Description is required");
        if (formData.supportContact && !formData.supportContact.includes('@')) {
          errors.push("Support Contact should be a valid email");
        }
        break;

      case 2:
        if (!formData.primaryUsers.trim()) errors.push("Primary Users is required");
        if (!formData.clinicalIndications.trim()) errors.push("Clinical Indications is required");
        if (!formData.patientTargetGroup.trim()) errors.push("Patient Target Group is required");
        break;

      case 3:
        if (!formData.datasetName.trim()) errors.push("Dataset Name is required");
        if (!formData.datasetOrigin.trim()) errors.push("Dataset Origin is required");
        if (!formData.dataDistribution.trim()) errors.push("Data Distribution Summary is required");
        if (!formData.dataRepresentativeness.trim()) errors.push("Data Representativeness is required");
        if (!formData.dataGovernance.trim()) errors.push("Data Governance is required");
        if (formData.datasetSize && isNaN(Number(formData.datasetSize))) {
          errors.push("Dataset Size must be a number");
        }
        break;

      case 4:
        if (!formData.inputFeatures.trim()) errors.push("Input Features is required");
        if (!formData.outputFeatures.trim()) errors.push("Output Features is required");
        break;

      case 5:
        if (!formData.validationDatasets.trim()) errors.push("Validation Datasets is required");
        if (!formData.claimedMetrics.trim()) errors.push("Claimed Metrics is required");
        break;

      case 6:
        if (!formData.developmentWorkflow.trim()) errors.push("Development Workflow is required");
        if (!formData.trainingProcedure.trim()) errors.push("Training Procedure is required");
        break;

      case 7:
        if (!formData.benefitRiskSummary.trim()) errors.push("Benefit/Risk Summary is required");
        if (!formData.caveatsLimitations.trim()) errors.push("Caveats & Limitations is required");
        break;
    }

    return errors;
  };

  const saveSection = async (sectionNumber: number) => {
    setSavingSection(sectionNumber);

    const errors = validateSection(sectionNumber);
    setSectionErrors(prev => ({ ...prev, [sectionNumber]: errors }));

    if (errors.length > 0) {
      setSavingSection(null);
      return false;
    }

    try {
      const savedData = localStorage.getItem('modelCardDraft') || '{}';
      const draft = JSON.parse(savedData);
      draft[`section${sectionNumber}`] = { ...formData, savedAt: new Date().toISOString() };
      localStorage.setItem('modelCardDraft', JSON.stringify(draft));

      setSectionSaved(prev => ({ ...prev, [sectionNumber]: true }));

      setTimeout(() => {
        setSectionSaved(prev => ({ ...prev, [sectionNumber]: false }));
      }, 3000);

      setSavingSection(null);
      return true;
    } catch (error) {
      console.error('Error saving section:', error);
      setSavingSection(null);
      return false;
    }
  };

  const validateAllSections = (): { valid: boolean; firstErrorSection: number | null; allErrors: {[key: number]: string[]} } => {
    const allErrors: {[key: number]: string[]} = {};
    let firstErrorSection: number | null = null;

    for (let i = 1; i <= 7; i++) {
      const errors = validateSection(i);
      if (errors.length > 0) {
        allErrors[i] = errors;
        if (firstErrorSection === null) {
          firstErrorSection = i;
        }
      }
    }

    setSectionErrors(allErrors);
    return {
      valid: Object.keys(allErrors).length === 0,
      firstErrorSection,
      allErrors
    };
  };

  const fetchCdmSources = async () => {
    if (!formData.omopWebApiUrl) {
      setOhdsiError('Please enter a WebAPI URL');
      return;
    }

    setOhdsiLoading(true);
    setOhdsiError('');
    setCdmSources([]);

    try {
      const proxyUrl = `http://localhost:8000/api/ohdsi/sources?webapi_url=${encodeURIComponent(formData.omopWebApiUrl)}`;
      const response = await fetch(proxyUrl, {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to fetch sources: ${response.status}`);
      }

      const sources = await response.json();
      setCdmSources(sources);

      if (sources.length === 0) {
        setOhdsiError('No CDM sources found');
      }
    } catch (error: any) {
      console.error('Error fetching CDM sources:', error);
      setOhdsiError(`Failed to connect to WebAPI: ${error.message}`);
    } finally {
      setOhdsiLoading(false);
    }
  };

  const fetchCohortDetails = async () => {
    if (!formData.omopWebApiUrl || !formData.omopCohortId || !formData.omopSelectedSource) {
      setOhdsiError('Please enter WebAPI URL, select a source, and enter a Cohort ID');
      return;
    }

    setFetchingCohort(true);
    setOhdsiError('');
    setCohortDetails(null);
    setHeraclesData(null);

    try {
      const cohortId = formData.omopCohortId;

      const proxyUrl = `http://localhost:8000/api/ohdsi/cohort/${cohortId}/full?webapi_url=${encodeURIComponent(formData.omopWebApiUrl)}&source_key=${encodeURIComponent(formData.omopSelectedSource)}`;

      const response = await fetch(proxyUrl, {
        headers: { 'Accept': 'application/json' }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Cohort ${cohortId} not found`);
      }

      const cohortData = await response.json();

      const details = {
        name: cohortData.name,
        description: cohortData.description,
        id: cohortData.id,
        personCount: cohortData.personCount || 'N/A',
        status: cohortData.status || 'UNKNOWN',
        createdDate: cohortData.createdDate,
        modifiedDate: cohortData.modifiedDate
      };

      setCohortDetails(details);

      handleInputChange('omopCohortName', details.name || '');
      handleInputChange('omopCohortSize', details.personCount?.toString() || '');
      handleInputChange('omopCohortStatus', details.status || '');

      handleInputChange('datasetName', `OHDSI Cohort: ${details.name}`);
      if (details.personCount !== 'N/A') {
        handleInputChange('datasetSize', details.personCount?.toString() || '');
      }

    } catch (error: any) {
      console.error('Error fetching cohort:', error);
      setOhdsiError(`Failed to fetch cohort: ${error.message}`);
    } finally {
      setFetchingCohort(false);
    }
  };

  const createNewCohort = async () => {
    if (!formData.omopWebApiUrl || !newCohortName || !cohortCriteria.primaryConditionConceptId) {
      setOhdsiError('Please enter WebAPI URL, cohort name, and primary condition');
      return;
    }

    setCreatingCohort(true);
    setOhdsiError('');

    try {
      const response = await fetch('http://localhost:8000/api/ohdsi/cohort/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({
          webapi_url: formData.omopWebApiUrl,
          cohort_name: newCohortName,
          description: newCohortDescription,
          criteria: {
            primary_condition_concept_id: parseInt(cohortCriteria.primaryConditionConceptId),
            primary_condition_name: cohortCriteria.primaryConditionName,
            age_min: cohortCriteria.ageMin ? parseInt(cohortCriteria.ageMin) : null,
            age_max: cohortCriteria.ageMax ? parseInt(cohortCriteria.ageMax) : null,
            gender_concept_id: cohortCriteria.genderConceptId ? parseInt(cohortCriteria.genderConceptId) : null,
            observation_period_days: parseInt(cohortCriteria.observationPeriodDays) || 365
          }
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to create cohort: ${response.status}`);
      }

      const cohortData = await response.json();

      handleInputChange('omopCohortId', cohortData.id?.toString() || '');
      handleInputChange('omopCohortName', cohortData.name || newCohortName);
      handleInputChange('omopCohortStatus', 'PENDING');

      setCohortDetails({
        name: cohortData.name || newCohortName,
        description: newCohortDescription,
        id: cohortData.id,
        personCount: 'Pending generation',
        status: 'PENDING'
      });

      if (!formData.datasetName) {
        handleInputChange('datasetName', `OHDSI Cohort: ${cohortData.name || newCohortName}`);
      }

      setOhdsiError('');

    } catch (error: any) {
      console.error('Error creating cohort:', error);
      setOhdsiError(`Failed to create cohort: ${error.message}`);
    } finally {
      setCreatingCohort(false);
    }
  };

  const fetchHeraclesAndAutoFill = async () => {
    if (!formData.omopWebApiUrl || !formData.omopCohortId || !formData.omopSelectedSource) {
      setOhdsiError('Please connect to WebAPI, select a source, and fetch a cohort first');
      return;
    }

    setFetchingHeracles(true);
    setOhdsiError('');

    try {
      const response = await fetch(
        `http://localhost:8000/api/ohdsi/cohort/${formData.omopCohortId}/heracles?webapi_url=${encodeURIComponent(formData.omopWebApiUrl)}&source_key=${encodeURIComponent(formData.omopSelectedSource)}`,
        {
          headers: { 'Accept': 'application/json' }
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to fetch Heracles reports');
      }

      const heraclesResult = await response.json();
      setHeraclesData(heraclesResult);

      if (heraclesResult.demographics) {
        const demo = heraclesResult.demographics;

        handleInputChange('demographicsAge', demo.age_distribution || '');
        handleInputChange('demographicsGender', demo.gender_distribution || '');

        const raceEthParts = [];
        if (demo.race_distribution) {
          raceEthParts.push(`Race: ${demo.race_distribution}`);
        }
        if (demo.ethnicity_distribution) {
          raceEthParts.push(`Ethnicity: ${demo.ethnicity_distribution}`);
        }
        handleInputChange('demographicsEthnicity', raceEthParts.join('. ') || '');
      }

      handleInputChange('populationChars', heraclesResult.population_characteristics || '');
      handleInputChange('dataDistribution', heraclesResult.data_distribution_summary || '');
      handleInputChange('dataRepresentativeness', heraclesResult.data_representativeness_template || '');
      handleInputChange('dataGovernance', heraclesResult.data_governance_template || '');

      if (heraclesResult.concept_sets && heraclesResult.concept_sets.length > 0) {
        const conceptIds = heraclesResult.concept_sets
          .map((cs: any) => cs.concept_ids?.join(', '))
          .filter(Boolean)
          .join('; ');
        const conceptNames = heraclesResult.concept_sets
          .map((cs: any) => cs.name)
          .filter(Boolean)
          .join(', ');

        handleInputChange('omopConceptSetIds', conceptIds || '');
        handleInputChange('omopConceptSetNames', conceptNames || '');
      } else {
        handleInputChange('omopConceptSetIds', '');
        handleInputChange('omopConceptSetNames', '');
      }

      handleInputChange('collectionPeriod', heraclesResult.collection_period || '');

      if (heraclesResult.cohort_name) {
        handleInputChange('datasetName', `OHDSI Cohort: ${heraclesResult.cohort_name}`);
      }

      if (heraclesResult.person_count) {
        handleInputChange('datasetSize', heraclesResult.person_count.toString());
      }

      handleInputChange('datasetOrigin', `OMOP CDM - ${formData.omopSelectedSource} (Electronic Health Records)`);

      if (heraclesResult.condition_summary && heraclesResult.condition_summary.length > 0) {
        const topConditions = heraclesResult.condition_summary
          .slice(0, 5)
          .map((c: any) => `${c.name} (${c.percent_persons}%)`)
          .join(', ');

        handleInputChange('demographicsOther', `Top conditions: ${topConditions}`);
      } else {
        handleInputChange('demographicsOther', '');
      }

    } catch (error: any) {
      console.error('Error fetching Heracles data:', error);
      setOhdsiError(`Failed to fetch characterization data: ${error.message}`);
    } finally {
      setFetchingHeracles(false);
    }
  };

  const handleSubmit = async () => {
    const validation = validateAllSections();

    if (!validation.valid && validation.firstErrorSection) {
      setCurrentSection(validation.firstErrorSection);

      const sectionElement = document.getElementById(`section-${validation.firstErrorSection}`);
      if (sectionElement) {
        sectionElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }

      setError(`Please fix errors in Section ${validation.firstErrorSection} before submitting`);
      return;
    }

    setLoading(true);
    setError('');

    if (revising) {
      if (!revisionNotes.trim()) {
        setError('Revision notes are required');
        setLoading(false);
        toast.error('Please describe what changed');
        return;
      }
      try {
        const walletAddress = getWalletAddress();
        if (!walletAddress) throw new Error('Wallet address not found');
        const r = await fetch('http://localhost:8000/api/model-cards/revise', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            token_id: Number(revising),
            revisor_address: walletAddress,
            updated_metadata: buildMetadataPayload(formData),
            revision_notes: revisionNotes.trim(),
          }),
        });
        if (!r.ok) {
          const d = await r.json().catch(() => ({}));
          throw new Error(d.detail || `HTTP ${r.status}`);
        }
        toast.success('Revision submitted on chain');
        setSuccess(true);
        setTimeout(() => { window.location.href = `/model/${revising}`; }, 1500);
        return;
      } catch (err: any) {
        setError(err.message || 'Revision failed');
        toast.error(err.message || 'Revision failed');
        setLoading(false);
        return;
      }
    }

    try {
      const endpoint = createMode === 'version'
        ? 'http://localhost:8000/api/smart-model-card/create-version'
        : 'http://localhost:8000/api/smart-model-card/create';

      const modelName = createMode === 'version' && selectedParentModel
        ? selectedParentModel
        : formData.modelName;

      const walletAddress = getWalletAddress();
      if (!walletAddress) {
        throw new Error("Wallet address not found. Please reconnect your wallet.");
      }
      const developerAddress = walletAddress;

      const creatorUuid = localStorage.getItem('uuid');

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          developer_address: developerAddress,
          creator_uuid: creatorUuid,
          model_details: {
            model_name: modelName,
            version: formData.version,
            developer_organization: formData.developerOrg,
            release_date: formData.releaseDate || new Date().toISOString().split('T')[0],
            description: formData.description,
            clinical_function: formData.clinicalFunction,
            intended_purpose: formData.intendedPurpose,
            algorithms_used: formData.algorithmsUsed,
            licensing: formData.licensing || "Not specified",
            gmdn_code: formData.gmdnCode || null,
            support_contact: formData.supportContact,
            literature_references: formData.literatureRefs
              ? formData.literatureRefs.split('\n').filter((ref: string) => ref.trim())
              : [],
            information_significance: formData.informationSignificance || null,
            basic_udi_di: formData.basicUdiDi || null,
            udi_di: formData.udiDi || null,
            regulatory_classifications: formData.regulatoryClassifications
              ? formData.regulatoryClassifications.split('\n').map((line: string) => {
                  const parts = line.split('|').map((p: string) => p.trim());
                  if (parts.length < 2 || !parts[0]) return null;
                  return {
                    framework: parts[0] || '',
                    class: parts[1] || '',
                    rule: parts[2] || '',
                    pathway: parts[3] || '',
                  };
                }).filter(Boolean)
              : [],
            clinical_study_references: formData.clinicalStudyReferences
              ? formData.clinicalStudyReferences.split('\n').filter((s: string) => s.trim())
              : [],
            logo_image: formData.logoImage || null,
          },
          intended_use: {
            primary_intended_users: formData.primaryUsers,
            clinical_indications: formData.clinicalIndications,
            patient_target_group: formData.patientTargetGroup,
            intended_use_environment: formData.useEnvironment,
            contraindications: formData.contraindications || null,
            out_of_scope_applications: formData.outOfScope || null,
            warnings: formData.warnings || null
          },
          data_factors: {
            source_datasets: [{
              name: formData.datasetName,
              origin: formData.datasetOrigin,
              size: parseInt(formData.datasetSize) || 0,
              collection_period: formData.collectionPeriod,
              population_characteristics: formData.populationChars,
              demographics: {
                age: formData.demographicsAge || null,
                gender: formData.demographicsGender || null,
                ethnicity: formData.demographicsEthnicity || null,
                other: formData.demographicsOther || null
              }
            }],
            data_distribution_summary: formData.dataDistribution,
            data_representativeness: formData.dataRepresentativeness,
            data_governance: formData.dataGovernance,
            omop_integration: formData.useOMOP ? {
              enabled: true,
              integration_method: formData.omopIntegrationMethod,
              webapi_url: formData.omopWebApiUrl || null,
              selected_source: formData.omopSelectedSource || null,
              cohort: formData.omopCohortId ? {
                id: formData.omopCohortId,
                name: formData.omopCohortName || null,
                size: parseInt(formData.omopCohortSize) || null,
                status: formData.omopCohortStatus || null
              } : null,
              include_heracles: formData.omopIncludeHeracles,
              concept_set_ids: formData.omopConceptSetIds
                ? formData.omopConceptSetIds.split(',').map((id: string) => id.trim()).filter(Boolean)
                : [],
              concept_set_names: formData.omopConceptSetNames
                ? formData.omopConceptSetNames.split(',').map((name: string) => name.trim()).filter(Boolean)
                : []
            } : null
          },
          features_outputs: {
            input_features: formData.inputFeatures,
            output_features: formData.outputFeatures,
            feature_type_distribution: formData.featureTypeDistribution || null,
            uncertainty_quantification: formData.uncertaintyQuantification || null,
            output_interpretability: formData.outputInterpretability || null
          },
          performance_validation: {
            validation_datasets: formData.validationDatasets,
            claimed_metrics: formData.claimedMetrics,
            validated_metrics: formData.validatedMetrics || null,
            metric_validation_status: formData.metricValidationStatus || "claimed",
            calibration_analysis: formData.calibrationAnalysis || null,
            fairness_assessment: formData.fairnessAssessment || null
          },
          methodology: {
            model_development_workflow: formData.developmentWorkflow,
            training_procedure: formData.trainingProcedure,
            data_preprocessing: formData.dataPreprocessing,
            synthetic_data_usage: formData.syntheticDataUsage || null,
            explainable_ai_methods: formData.explainableAI || null,
            global_vs_local_interpretability: formData.globalVsLocalInterpretability || null
          },
          additional_info: {
            benefit_risk_summary: formData.benefitRiskSummary,
            ethical_considerations: formData.ethicalConsiderations || null,
            caveats_limitations: formData.caveatsLimitations,
            recommendations_for_safe_use: formData.recommendationsSafeUse,
            post_market_surveillance_plan: formData.postMarketSurveillancePlan || null,
            explainability_recommendations: formData.explainabilityRecommendations || null,
            supporting_documents: formData.supportingDocuments
              ? formData.supportingDocuments.split('\n').map((s: string) => s.trim()).filter(Boolean)
              : []
          },
          lineage: (Number(formData.relation) > 0 || formData.envelopeText)
            ? {
                ...(Number(formData.relation) > 0 && { relation: Number(formData.relation) }),
                ...(formData.envelopeText && { envelope_text: formData.envelopeText }),
              }
            : null,
        })
      });

      if (response.ok) {
        setSuccess(true);
        setTimeout(() => {
          window.location.href = '/workflow';
        }, 2000);
      } else {
        const errorData = await response.json().catch(() => null);
        console.error('API Error:', errorData);
        const raw = errorData?.detail || errorData?.message || `HTTP ${response.status}`;
        const errorMessage = typeof raw === 'string'
          ? (raw.length > 280 ? raw.slice(0, 277) + '…' : raw)
          : 'Error creating model card';

        const isDuplicate =
          response.status === 409 ||
          /already exists|owned by other controller/i.test(errorMessage);

        setError(errorMessage);
        toast.error(isDuplicate ? 'Model name already taken' : 'Failed to create model card', {
          description: errorMessage,
        });

        if (isDuplicate) {
          setCurrentSection(1);
          const el = document.getElementById('section-1');
          if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }
    } catch (err) {
      console.error('Error:', err);
      const msg = 'Network error - please check if the backend is running';
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const sections = [
    { num: 1, title: "Model Details" },
    { num: 2, title: "Intended Use" },
    { num: 3, title: "Data & Factors" },
    { num: 4, title: "Features & Outputs" },
    { num: 5, title: "Performance & Validation" },
    { num: 6, title: "Methodology" },
    { num: 7, title: "Additional Info" }
  ];

  const renderSectionHeader = (sectionNum: number, title: string) => (
    <div className="mb-6" id={`section-${sectionNum}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="meta">Section {String(sectionNum).padStart(2, '0')}</p>
          <h3 className="text-xl font-semibold tracking-tight mt-1">{title}</h3>
        </div>
        <div className="flex items-center gap-3">
          {sectionSaved[sectionNum] && (
            <span className="text-sm text-green-600 flex items-center gap-1">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Saved
            </span>
          )}
          <button
            type="button"
            onClick={() => saveSection(sectionNum)}
            disabled={savingSection === sectionNum}
            className="px-4 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg border border-gray-300 transition-colors flex items-center gap-2 disabled:opacity-50"
          >
            {savingSection === sectionNum ? (
              <>
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Saving...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                </svg>
                Save Section
              </>
            )}
          </button>
        </div>
      </div>

      {sectionErrors[sectionNum] && sectionErrors[sectionNum].length > 0 && (
        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-start gap-2">
            <svg className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <div className="font-medium text-red-800 text-sm">Please fix the following errors:</div>
              <ul className="mt-1 text-sm text-red-700 list-disc list-inside">
                {sectionErrors[sectionNum].map((error, idx) => (
                  <li key={idx}>{error}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  const renderSectionContent = () => {
    switch(currentSection) {
      case 1:
        return (
          <div className="space-y-4">
            {renderSectionHeader(1, "Model Details")}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Model Name *</label>
              {createMode === 'version' ? (
                <div className="w-full px-4 py-2 border border-purple-300 bg-purple-50 rounded-lg text-purple-900 font-medium">
                  {selectedParentModel || '-- Select a parent model above --'}
                </div>
              ) : (
                <input
                  type="text"
                  value={formData.modelName}
                  onChange={(e) => handleInputChange('modelName', e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="Model name"
                  required
                />
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Version * {createMode === 'version' && <span className="text-purple-600">(Auto-generated)</span>}
                </label>
                {createMode === 'version' ? (
                  <div className="w-full px-4 py-2 border border-purple-300 bg-purple-50 rounded-lg text-purple-900 font-medium">
                    Will be auto-incremented
                  </div>
                ) : (
                  <input
                    type="text"
                    value={formData.version}
                    onChange={(e) => handleInputChange('version', e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="1.0.0"
                    required
                  />
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Release Date</label>
                <input
                  type="date"
                  value={formData.releaseDate}
                  onChange={(e) => handleInputChange('releaseDate', e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Developer Organization *</label>
              <input
                type="text"
                value={formData.developerOrg}
                onChange={(e) => handleInputChange('developerOrg', e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Organization name"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Description *</label>
              <textarea
                value={formData.description}
                onChange={(e) => handleInputChange('description', e.target.value)}
                rows={4}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Describe the model's purpose, capabilities, and key features..."
                required
              />
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Clinical Function *</label>
                <select
                  value={formData.clinicalFunction}
                  onChange={(e) => handleInputChange('clinicalFunction', e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="decision_support">Decision Support</option>
                  <option value="screening">Screening</option>
                  <option value="diagnosis">Diagnosis</option>
                  <option value="triage">Triage</option>
                  <option value="monitoring">Monitoring</option>
                  <option value="workflow_support">Workflow Support</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Intended Purpose</label>
                <select
                  value={formData.intendedPurpose}
                  onChange={(e) => handleInputChange('intendedPurpose', e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="decision_support">Decision Support</option>
                  <option value="screening">Screening</option>
                  <option value="diagnosis">Diagnosis</option>
                  <option value="triage">Triage</option>
                  <option value="monitoring">Monitoring</option>
                  <option value="prognosis">Prognosis</option>
                  <option value="workflow_support">Workflow Support</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Licensing</label>
                <input
                  type="text"
                  value={formData.licensing}
                  onChange={(e) => handleInputChange('licensing', e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="MIT"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Algorithms Used *</label>
              <input
                type="text"
                value={formData.algorithmsUsed}
                onChange={(e) => handleInputChange('algorithmsUsed', e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="e.g., XGBoost Classifier, Random Forest"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Support Contact (Email) *</label>
              <input
                type="email"
                value={formData.supportContact}
                onChange={(e) => handleInputChange('supportContact', e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="ai-team@hospital.org"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">GMDN Code</label>
              <input
                type="text"
                value={formData.gmdnCode}
                onChange={(e) => handleInputChange('gmdnCode', e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Optional GMDN code"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Literature References</label>
              <textarea
                value={formData.literatureRefs}
                onChange={(e) => handleInputChange('literatureRefs', e.target.value)}
                rows={2}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Research papers, citations, DOIs..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Clinical Study References</label>
              <textarea
                value={formData.clinicalStudyReferences}
                onChange={(e) => handleInputChange('clinicalStudyReferences', e.target.value)}
                rows={2}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="One reference per line (e.g., ClinicalTrials.gov NCT...)"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Information Significance</label>
                <select
                  value={formData.informationSignificance}
                  onChange={(e) => handleInputChange('informationSignificance', e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="">- not specified -</option>
                  <option value="inform">Inform</option>
                  <option value="drive">Drive</option>
                  <option value="treat_or_diagnose">Treat or diagnose</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Logo / Image URL</label>
                <input
                  type="text"
                  value={formData.logoImage}
                  onChange={(e) => handleInputChange('logoImage', e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="https://..."
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Basic UDI-DI</label>
                <input
                  type="text"
                  value={formData.basicUdiDi}
                  onChange={(e) => handleInputChange('basicUdiDi', e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="EU MDR Basic UDI-DI"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">UDI-DI</label>
                <input
                  type="text"
                  value={formData.udiDi}
                  onChange={(e) => handleInputChange('udiDi', e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="UDI-DI"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Regulatory Classifications</label>
              <textarea
                value={formData.regulatoryClassifications}
                onChange={(e) => handleInputChange('regulatoryClassifications', e.target.value)}
                rows={3}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm"
                placeholder="One per line: framework | class | rule | pathway"
              />
              <p className="text-xs text-gray-500 mt-1">
                Format: <span className="font-mono">framework | class | rule | pathway</span>
                {' '} - e.g., <span className="font-mono">EU MDR | Class IIa | Rule 11 | CE-marked</span>
              </p>
            </div>

            {!revising && (
              <LineagePreviewPanel
                modelName={formData.modelName}
                creator={getWalletAddress() || ''}
                relation={formData.relation}
                setRelation={(v) => handleInputChange('relation', v)}
                envelopeText={formData.envelopeText}
                setEnvelopeText={(v) => handleInputChange('envelopeText', v)}
              />
            )}
          </div>
        );

      case 2:
        return (
          <div className="space-y-4">
            {renderSectionHeader(2, "Intended Use & Clinical Context")}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Primary Intended Users *</label>
              <input
                type="text"
                value={formData.primaryUsers}
                onChange={(e) => handleInputChange('primaryUsers', e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="e.g., Primary care physicians, Clinical researchers"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Clinical Indications *</label>
              <textarea
                value={formData.clinicalIndications}
                onChange={(e) => handleInputChange('clinicalIndications', e.target.value)}
                rows={3}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Describe clinical scenarios where this model should be used..."
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Patient Target Group *</label>
              <input
                type="text"
                value={formData.patientTargetGroup}
                onChange={(e) => handleInputChange('patientTargetGroup', e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="e.g., Adults aged 40-75 with pre-diabetes"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Use Environment *</label>
              <select
                value={formData.useEnvironment}
                onChange={(e) => handleInputChange('useEnvironment', e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="hospital_inpatient">Hospital Inpatient</option>
                <option value="hospital_outpatient">Hospital Outpatient</option>
                <option value="clinic">Clinic</option>
                <option value="home">Home</option>
                <option value="mobile">Mobile</option>
                <option value="other">Other</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Contraindications</label>
              <textarea
                value={formData.contraindications}
                onChange={(e) => handleInputChange('contraindications', e.target.value)}
                rows={2}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="When should this model NOT be used?"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Out of Scope Applications</label>
              <textarea
                value={formData.outOfScope}
                onChange={(e) => handleInputChange('outOfScope', e.target.value)}
                rows={2}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Applications that are outside the intended scope..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Warnings</label>
              <textarea
                value={formData.warnings}
                onChange={(e) => handleInputChange('warnings', e.target.value)}
                rows={2}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Important warnings for users..."
              />
            </div>
          </div>
        );

      case 3:
        return (
          <div className="space-y-6">
            {renderSectionHeader(3, "Data & Factors")}

            <div className="surface p-5">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h4 className="font-semibold tracking-tight">
                    OMOP CDM Integration
                  </h4>
                  <p className="text-sm text-purple-700 mt-1">
                    Use standardized healthcare concepts from OMOP Common Data Model
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => handleInputChange('useOMOP', !formData.useOMOP)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    formData.useOMOP ? 'bg-purple-600' : 'bg-gray-300'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      formData.useOMOP ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>

              {formData.useOMOP && (
                <div className="mt-4 space-y-5 pt-4 border-t border-purple-200">
                  <div>
                    <label className="block text-sm font-medium text-purple-900 mb-3">
                      Choose integration method:
                    </label>
                    <div className="grid grid-cols-4 gap-3">
                      <button
                        type="button"
                        onClick={() => handleInputChange('omopIntegrationMethod', 'webapi')}
                        className={`p-3 rounded-lg border-2 text-left transition-all ${
                          formData.omopIntegrationMethod === 'webapi'
                            ? 'border-purple-500 bg-purple-100'
                            : 'border-purple-200 bg-white hover:border-purple-300'
                        }`}
                      >
                        
                        <div className="font-medium text-sm text-purple-900">Fetch Cohort</div>
                        <div className="text-xs text-purple-600">Existing cohort</div>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleInputChange('omopIntegrationMethod', 'create')}
                        className={`p-3 rounded-lg border-2 text-left transition-all ${
                          formData.omopIntegrationMethod === 'create'
                            ? 'border-purple-500 bg-purple-100'
                            : 'border-purple-200 bg-white hover:border-purple-300'
                        }`}
                      >
                        
                        <div className="font-medium text-sm text-purple-900">Create New</div>
                        <div className="text-xs text-purple-600">Build cohort</div>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleInputChange('omopIntegrationMethod', 'manual')}
                        className={`p-3 rounded-lg border-2 text-left transition-all ${
                          formData.omopIntegrationMethod === 'manual'
                            ? 'border-purple-500 bg-purple-100'
                            : 'border-purple-200 bg-white hover:border-purple-300'
                        }`}
                      >
                        
                        <div className="font-medium text-sm text-purple-900">Manual Entry</div>
                        <div className="text-xs text-purple-600">Enter concept IDs</div>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleInputChange('omopIntegrationMethod', 'local')}
                        className={`p-3 rounded-lg border-2 text-left transition-all ${
                          formData.omopIntegrationMethod === 'local'
                            ? 'border-purple-500 bg-purple-100'
                            : 'border-purple-200 bg-white hover:border-purple-300'
                        }`}
                      >
                        
                        <div className="font-medium text-sm text-purple-900">Local Data</div>
                        <div className="text-xs text-purple-600">Use saved cohort</div>
                      </button>
                    </div>
                  </div>

                  {formData.omopIntegrationMethod === 'webapi' && (
                    <div className="space-y-4 p-4 bg-white rounded-lg border border-purple-200">
                      <h5 className="font-medium text-purple-900 flex items-center gap-2">
                        OHDSI WebAPI Connection
                      </h5>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          OHDSI WebAPI URL *
                        </label>
                        <div className="flex gap-2">
                          <input
                            type="url"
                            value={formData.omopWebApiUrl}
                            onChange={(e) => handleInputChange('omopWebApiUrl', e.target.value)}
                            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                            placeholder="https://atlas.yourorg.org/WebAPI"
                          />
                          <button
                            type="button"
                            onClick={fetchCdmSources}
                            disabled={ohdsiLoading || !formData.omopWebApiUrl}
                            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                          >
                            {ohdsiLoading ? (
                              <>
                                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                </svg>
                                Connecting...
                              </>
                            ) : (
                              'Connect'
                            )}
                          </button>
                        </div>
                      </div>

                      {ohdsiError && (
                        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                          {ohdsiError}
                        </div>
                      )}

                      {cdmSources.length > 0 && (
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-2">
                            Available CDM Sources ({cdmSources.length})
                          </label>
                          <div className="grid grid-cols-2 gap-2">
                            {cdmSources.map((source: any, index: number) => (
                              <button
                                key={source.sourceKey || index}
                                type="button"
                                onClick={() => handleInputChange('omopSelectedSource', source.sourceKey || source.sourceId?.toString())}
                                className={`p-3 rounded-lg border text-left transition-all ${
                                  formData.omopSelectedSource === (source.sourceKey || source.sourceId?.toString())
                                    ? 'border-purple-500 bg-purple-50'
                                    : 'border-gray-200 bg-gray-50 hover:border-purple-300'
                                }`}
                              >
                                <div className="font-medium text-sm text-gray-900">
                                  {source.sourceKey || source.sourceName}
                                </div>
                                <div className="text-xs text-gray-500">
                                  {source.sourceName || source.sourceDialect}
                                </div>
                              </button>
                            ))}
                          </div>
                        </div>
                      )}

                      {formData.omopSelectedSource && (
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Cohort ID *
                          </label>
                          <div className="flex gap-2">
                            <input
                              type="number"
                              value={formData.omopCohortId}
                              onChange={(e) => handleInputChange('omopCohortId', e.target.value)}
                              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                              placeholder="Enter cohort ID (e.g., 168)"
                            />
                            <button
                              type="button"
                              onClick={fetchCohortDetails}
                              disabled={fetchingCohort || !formData.omopCohortId}
                              className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                            >
                              {fetchingCohort ? (
                                <>
                                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                  </svg>
                                  Fetching...
                                </>
                              ) : (
                                'Fetch Cohort'
                              )}
                            </button>
                          </div>
                        </div>
                      )}

                      {formData.omopSelectedSource && (
                        <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                          <div>
                            <div className="font-medium text-sm text-gray-900">Include Heracles Reports</div>
                            <div className="text-xs text-gray-500">Include characterization analysis data</div>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleInputChange('omopIncludeHeracles', !formData.omopIncludeHeracles)}
                            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                              formData.omopIncludeHeracles ? 'bg-purple-600' : 'bg-gray-300'
                            }`}
                          >
                            <span
                              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                                formData.omopIncludeHeracles ? 'translate-x-6' : 'translate-x-1'
                              }`}
                            />
                          </button>
                        </div>
                      )}

                      {cohortDetails && (
                        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg">
                          <div className="flex items-start gap-3">
                            <div className="text-2xl">Done</div>
                            <div className="flex-1">
                              <div className="font-semibold text-emerald-900">
                                Successfully fetched cohort: {cohortDetails.name}
                              </div>
                              <div className="text-sm text-emerald-700 mt-1">
                                Cohort has <strong>{cohortDetails.personCount}</strong> persons
                                (status: <span className={`font-medium ${cohortDetails.status === 'COMPLETE' ? 'text-emerald-600' : 'text-amber-600'}`}>
                                  {cohortDetails.status}
                                </span>)
                              </div>
                              {cohortDetails.description && (
                                <div className="text-xs text-emerald-600 mt-2">
                                  {cohortDetails.description}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      )}

                      {cohortDetails && formData.omopIncludeHeracles && (
                        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                          <div className="flex items-center justify-between">
                            <div>
                              <div className="font-medium text-sm text-blue-900">Auto-fill Section 3 Fields</div>
                              <div className="text-xs text-blue-600">Populate demographics, distribution, and characteristics from Heracles reports</div>
                            </div>
                            <button
                              type="button"
                              onClick={fetchHeraclesAndAutoFill}
                              disabled={fetchingHeracles}
                              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                            >
                              {fetchingHeracles ? (
                                <>
                                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                  </svg>
                                  Loading...
                                </>
                              ) : (
                                <>Auto-fill Fields</>
                              )}
                            </button>
                          </div>
                          {heraclesData && (
                            <div className="mt-3 space-y-2">
                              <div className="text-xs text-blue-700 font-medium">
                                Demographics and characterization data loaded successfully
                              </div>
                              {heraclesData.heracles_available && (
                                <div className="text-xs text-blue-600 bg-blue-100 p-2 rounded">
                                  <div className="font-medium mb-1">Data Retrieved:</div>
                                  <ul className="list-disc list-inside space-y-0.5">
                                    {heraclesData.person_count && (
                                      <li>Cohort size: {heraclesData.person_count.toLocaleString()} subjects</li>
                                    )}
                                    {heraclesData.demographics?.age_distribution && (
                                      <li>Age: {heraclesData.demographics.age_distribution}</li>
                                    )}
                                    {heraclesData.demographics?.gender_distribution && (
                                      <li>Gender: {heraclesData.demographics.gender_distribution}</li>
                                    )}
                                    {heraclesData.condition_summary?.length > 0 && (
                                      <li>Conditions: {heraclesData.condition_summary.length} recorded</li>
                                    )}
                                    {heraclesData.concept_sets?.length > 0 && (
                                      <li>Concept sets: {heraclesData.concept_sets.length} defined</li>
                                    )}
                                  </ul>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {formData.omopIntegrationMethod === 'create' && (
                    <div className="space-y-4 p-4 bg-white rounded-lg border border-purple-200">
                      <h5 className="font-medium text-purple-900 flex items-center gap-2">
                        Create New Cohort
                      </h5>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          OHDSI WebAPI URL *
                        </label>
                        <div className="flex gap-2">
                          <input
                            type="url"
                            value={formData.omopWebApiUrl}
                            onChange={(e) => handleInputChange('omopWebApiUrl', e.target.value)}
                            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                            placeholder="https://atlas.yourorg.org/WebAPI"
                          />
                          <button
                            type="button"
                            onClick={fetchCdmSources}
                            disabled={ohdsiLoading || !formData.omopWebApiUrl}
                            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                          >
                            {ohdsiLoading ? 'Connecting...' : 'Connect'}
                          </button>
                        </div>
                      </div>

                      {ohdsiError && (
                        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                          {ohdsiError}
                        </div>
                      )}

                      {cdmSources.length > 0 && (
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-2">
                            Select CDM Source *
                          </label>
                          <select
                            value={formData.omopSelectedSource}
                            onChange={(e) => handleInputChange('omopSelectedSource', e.target.value)}
                            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                          >
                            <option value="">-- Select a source --</option>
                            {cdmSources.map((source: any, index: number) => (
                              <option key={source.sourceKey || index} value={source.sourceKey || source.sourceId?.toString()}>
                                {source.sourceKey || source.sourceName} - {source.sourceName || source.sourceDialect}
                              </option>
                            ))}
                          </select>
                        </div>
                      )}

                      {formData.omopSelectedSource && (
                        <div className="space-y-4 p-4 bg-gray-50 rounded-lg">
                          <h6 className="font-medium text-gray-800">Cohort Definition</h6>

                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <label className="block text-sm font-medium text-gray-700 mb-1">Cohort Name *</label>
                              <input
                                type="text"
                                value={newCohortName}
                                onChange={(e) => setNewCohortName(e.target.value)}
                                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                                placeholder="e.g., COPD Patients 2023"
                              />
                            </div>
                            <div>
                              <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                              <input
                                type="text"
                                value={newCohortDescription}
                                onChange={(e) => setNewCohortDescription(e.target.value)}
                                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                                placeholder="Brief description"
                              />
                            </div>
                          </div>

                          <div className="border-t border-gray-200 pt-4">
                            <h6 className="font-medium text-gray-800 mb-3">Primary Criteria</h6>

                            <div className="grid grid-cols-2 gap-4">
                              <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                  Primary Condition Concept ID *
                                </label>
                                <input
                                  type="number"
                                  value={cohortCriteria.primaryConditionConceptId}
                                  onChange={(e) => setCohortCriteria({...cohortCriteria, primaryConditionConceptId: e.target.value})}
                                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                                  placeholder="e.g., 255573 (COPD)"
                                />
                                <p className="text-xs text-gray-500 mt-1">
                                  Find concept IDs at <a href="https://athena.ohdsi.org" target="_blank" rel="noopener noreferrer" className="text-purple-600 hover:underline">athena.ohdsi.org</a>
                                </p>
                              </div>
                              <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                  Condition Name
                                </label>
                                <input
                                  type="text"
                                  value={cohortCriteria.primaryConditionName}
                                  onChange={(e) => setCohortCriteria({...cohortCriteria, primaryConditionName: e.target.value})}
                                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                                  placeholder="e.g., Chronic obstructive pulmonary disease"
                                />
                              </div>
                            </div>

                            <div className="grid grid-cols-3 gap-4 mt-4">
                              <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Age Min</label>
                                <input
                                  type="number"
                                  value={cohortCriteria.ageMin}
                                  onChange={(e) => setCohortCriteria({...cohortCriteria, ageMin: e.target.value})}
                                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                                  placeholder="18"
                                />
                              </div>
                              <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Age Max</label>
                                <input
                                  type="number"
                                  value={cohortCriteria.ageMax}
                                  onChange={(e) => setCohortCriteria({...cohortCriteria, ageMax: e.target.value})}
                                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                                  placeholder="85"
                                />
                              </div>
                              <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Observation Period (days)</label>
                                <input
                                  type="number"
                                  value={cohortCriteria.observationPeriodDays}
                                  onChange={(e) => setCohortCriteria({...cohortCriteria, observationPeriodDays: e.target.value})}
                                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                                  placeholder="365"
                                />
                              </div>
                            </div>

                            <div className="mt-4">
                              <label className="block text-sm font-medium text-gray-700 mb-1">Gender (Optional)</label>
                              <select
                                value={cohortCriteria.genderConceptId}
                                onChange={(e) => setCohortCriteria({...cohortCriteria, genderConceptId: e.target.value})}
                                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                              >
                                <option value="">All genders</option>
                                <option value="8507">Male (8507)</option>
                                <option value="8532">Female (8532)</option>
                              </select>
                            </div>
                          </div>

                          <div className="flex justify-end pt-4 border-t border-gray-200">
                            <button
                              type="button"
                              onClick={createNewCohort}
                              disabled={creatingCohort || !newCohortName || !cohortCriteria.primaryConditionConceptId}
                              className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                            >
                              {creatingCohort ? (
                                <>
                                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                  </svg>
                                  Creating...
                                </>
                              ) : (
                                'Create Cohort'
                              )}
                            </button>
                          </div>
                        </div>
                      )}

                      {cohortDetails && formData.omopIntegrationMethod === 'create' && (
                        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg">
                          <div className="flex items-start gap-3">
                            <div className="text-2xl">Done</div>
                            <div className="flex-1">
                              <div className="font-semibold text-emerald-900">
                                Cohort created: {cohortDetails.name}
                              </div>
                              <div className="text-sm text-emerald-700 mt-1">
                                Cohort ID: <strong>{cohortDetails.id}</strong> - Status: {cohortDetails.status}
                              </div>
                              <div className="text-xs text-emerald-600 mt-2">
                                You may need to generate the cohort in ATLAS to get person counts.
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {formData.omopIntegrationMethod === 'manual' && (
                    <div className="space-y-4 p-4 bg-white rounded-lg border border-purple-200">
                      <h5 className="font-medium text-purple-900 flex items-center gap-2">
                        Manual Concept Entry
                      </h5>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          OMOP Concept Set IDs
                        </label>
                        <input
                          type="text"
                          value={formData.omopConceptSetIds}
                          onChange={(e) => handleInputChange('omopConceptSetIds', e.target.value)}
                          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                          placeholder="e.g., 201826, 4024659, 443454"
                        />
                        <p className="text-xs text-gray-500 mt-1">
                          Comma-separated OMOP concept IDs for conditions, drugs, procedures
                        </p>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Concept Set Names
                        </label>
                        <input
                          type="text"
                          value={formData.omopConceptSetNames}
                          onChange={(e) => handleInputChange('omopConceptSetNames', e.target.value)}
                          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                          placeholder="e.g., Type 2 Diabetes, Metformin, HbA1c Test"
                        />
                      </div>
                    </div>
                  )}

                  {formData.omopIntegrationMethod === 'local' && (
                    <div className="space-y-4 p-4 bg-white rounded-lg border border-purple-200">
                      <h5 className="font-medium text-purple-900 flex items-center gap-2">
                        Local Cohort Data
                      </h5>
                      <div className="p-4 bg-gray-50 rounded-lg text-center">
                        
                        <p className="text-sm text-gray-600 mb-3">
                          Upload a saved cohort JSON file or paste cohort data
                        </p>
                        <input
                          type="file"
                          accept=".json"
                          className="hidden"
                          id="cohort-upload"
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file) {
                              const reader = new FileReader();
                              reader.onload = (event) => {
                                try {
                                  const data = JSON.parse(event.target?.result as string);
                                  handleInputChange('omopCohortName', data.name || '');
                                  handleInputChange('omopCohortSize', data.personCount?.toString() || '');
                                  if (data.name && !formData.datasetName) {
                                    handleInputChange('datasetName', `OHDSI Cohort: ${data.name}`);
                                  }
                                } catch (err) {
                                  setOhdsiError('Invalid JSON file');
                                }
                              };
                              reader.readAsText(file);
                            }
                          }}
                        />
                        <label
                          htmlFor="cohort-upload"
                          className="inline-block px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 cursor-pointer transition-colors"
                        >
                          Choose File
                        </label>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-xl p-5">
              <h4 className="font-semibold text-blue-900 mb-4 flex items-center gap-2">
                Source Dataset
              </h4>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Dataset Name *</label>
                  <input
                    type="text"
                    value={formData.datasetName}
                    onChange={(e) => handleInputChange('datasetName', e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
                    placeholder="Hospital EHR Database"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Dataset Origin *</label>
                  <input
                    type="text"
                    value={formData.datasetOrigin}
                    onChange={(e) => handleInputChange('datasetOrigin', e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
                    placeholder="Academic Medical Center"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 mt-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Dataset Size (records) *</label>
                  <input
                    type="number"
                    value={formData.datasetSize}
                    onChange={(e) => handleInputChange('datasetSize', e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
                    placeholder="15000"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Collection Period *</label>
                  <input
                    type="text"
                    value={formData.collectionPeriod}
                    onChange={(e) => handleInputChange('collectionPeriod', e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
                    placeholder="2018-2023"
                    required
                  />
                </div>
              </div>
            </div>

            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-5">
              <h4 className="font-semibold text-emerald-900 mb-4 flex items-center gap-2">
                Demographics Breakdown
              </h4>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Age Distribution</label>
                  <input
                    type="text"
                    value={formData.demographicsAge}
                    onChange={(e) => handleInputChange('demographicsAge', e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent bg-white"
                    placeholder="e.g., Mean: 62, Range: 40-85"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Gender Distribution</label>
                  <input
                    type="text"
                    value={formData.demographicsGender}
                    onChange={(e) => handleInputChange('demographicsGender', e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent bg-white"
                    placeholder="e.g., 45% Female, 55% Male"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 mt-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Ethnicity Distribution</label>
                  <input
                    type="text"
                    value={formData.demographicsEthnicity}
                    onChange={(e) => handleInputChange('demographicsEthnicity', e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent bg-white"
                    placeholder="e.g., Caucasian 60%, African American 25%, Hispanic 10%, Other 5%"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Other Demographics</label>
                  <input
                    type="text"
                    value={formData.demographicsOther}
                    onChange={(e) => handleInputChange('demographicsOther', e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent bg-white"
                    placeholder="e.g., Socioeconomic factors, Insurance status"
                  />
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Population Characteristics *</label>
                <textarea
                  value={formData.populationChars}
                  onChange={(e) => handleInputChange('populationChars', e.target.value)}
                  rows={2}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="e.g., Adult patients with suspected cardiovascular disease, inclusion/exclusion criteria"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Data Distribution Summary *</label>
                <textarea
                  value={formData.dataDistribution}
                  onChange={(e) => handleInputChange('dataDistribution', e.target.value)}
                  rows={2}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="e.g., Balanced dataset with 30% positive cases, stratified sampling applied"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Data Representativeness *</label>
                <textarea
                  value={formData.dataRepresentativeness}
                  onChange={(e) => handleInputChange('dataRepresentativeness', e.target.value)}
                  rows={2}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="e.g., Representative of urban academic hospital population in North America"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Data Governance *</label>
                <textarea
                  value={formData.dataGovernance}
                  onChange={(e) => handleInputChange('dataGovernance', e.target.value)}
                  rows={2}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="e.g., IRB-approved protocol #12345, HIPAA-compliant, de-identified data"
                  required
                />
              </div>
            </div>
          </div>
        );

      case 4:
        return (
          <div className="space-y-4">
            {renderSectionHeader(4, "Features & Outputs")}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Input Features *</label>
              <textarea
                value={formData.inputFeatures}
                onChange={(e) => handleInputChange('inputFeatures', e.target.value)}
                rows={3}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Describe the input features (e.g., Age, BMI, Lab values, Medical history...)"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Output Features *</label>
              <textarea
                value={formData.outputFeatures}
                onChange={(e) => handleInputChange('outputFeatures', e.target.value)}
                rows={3}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Describe the model outputs (e.g., Risk score 0-100, Classification: High/Medium/Low risk...)"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Feature Type Distribution</label>
              <textarea
                value={formData.featureTypeDistribution}
                onChange={(e) => handleInputChange('featureTypeDistribution', e.target.value)}
                rows={2}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Distribution of feature types (e.g., 40% numerical, 30% categorical, 30% text)"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Uncertainty Quantification</label>
              <textarea
                value={formData.uncertaintyQuantification}
                onChange={(e) => handleInputChange('uncertaintyQuantification', e.target.value)}
                rows={2}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="How is uncertainty measured and reported? (e.g., Confidence intervals, Prediction intervals)"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Output Interpretability</label>
              <textarea
                value={formData.outputInterpretability}
                onChange={(e) => handleInputChange('outputInterpretability', e.target.value)}
                rows={2}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="How are outputs interpreted in clinical context?"
              />
            </div>
          </div>
        );

      case 5:
        return (
          <div className="space-y-4">
            {renderSectionHeader(5, "Performance & Validation")}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Validation Datasets *</label>
              <textarea
                value={formData.validationDatasets}
                onChange={(e) => handleInputChange('validationDatasets', e.target.value)}
                rows={3}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Describe validation datasets used (e.g., Hold-out test set of 3000 patients from 5 hospitals...)"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Claimed Metrics *</label>
              <textarea
                value={formData.claimedMetrics}
                onChange={(e) => handleInputChange('claimedMetrics', e.target.value)}
                rows={3}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Performance metrics (e.g., AUROC: 0.87, Sensitivity: 0.82, Specificity: 0.79)"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Validated Metrics</label>
              <textarea
                value={formData.validatedMetrics}
                onChange={(e) => handleInputChange('validatedMetrics', e.target.value)}
                rows={2}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Externally validated performance metrics"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Metric Validation Status <span className="text-red-500">*</span>
              </label>
              <select
                value={formData.metricValidationStatus}
                onChange={(e) => handleInputChange('metricValidationStatus', e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
              >
                <option value="claimed">Claimed</option>
                <option value="under_review">Under review</option>
                <option value="validated">Validated</option>
                <option value="failed">Failed validation</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Calibration Analysis</label>
              <textarea
                value={formData.calibrationAnalysis}
                onChange={(e) => handleInputChange('calibrationAnalysis', e.target.value)}
                rows={2}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Calibration assessment results (e.g., Calibration slope, Brier score)"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Fairness Assessment</label>
              <textarea
                value={formData.fairnessAssessment}
                onChange={(e) => handleInputChange('fairnessAssessment', e.target.value)}
                rows={2}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Fairness evaluation across demographic groups"
              />
            </div>

          </div>
        );

      case 6:
        return (
          <div className="space-y-4">
            {renderSectionHeader(6, "Methodology")}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Model Development Workflow *</label>
              <textarea
                value={formData.developmentWorkflow}
                onChange={(e) => handleInputChange('developmentWorkflow', e.target.value)}
                rows={3}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Describe the overall development process..."
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Training Procedure *</label>
              <textarea
                value={formData.trainingProcedure}
                onChange={(e) => handleInputChange('trainingProcedure', e.target.value)}
                rows={3}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Training methodology, hyperparameters, optimization..."
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Data Preprocessing *</label>
              <textarea
                value={formData.dataPreprocessing}
                onChange={(e) => handleInputChange('dataPreprocessing', e.target.value)}
                rows={3}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Data cleaning, normalization, feature engineering steps..."
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Synthetic Data Usage</label>
              <textarea
                value={formData.syntheticDataUsage}
                onChange={(e) => handleInputChange('syntheticDataUsage', e.target.value)}
                rows={2}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Describe synthetic data used in training or evaluation, or state none."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Explainable AI Methods</label>
              <textarea
                value={formData.explainableAI}
                onChange={(e) => handleInputChange('explainableAI', e.target.value)}
                rows={2}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="XAI techniques used (e.g., SHAP values, Feature importance, LIME)"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Global vs. Local Interpretability</label>
              <textarea
                value={formData.globalVsLocalInterpretability}
                onChange={(e) => handleInputChange('globalVsLocalInterpretability', e.target.value)}
                rows={2}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Describe global (cohort-level) vs local (per-prediction) interpretability."
              />
            </div>
          </div>
        );

      case 7:
        return (
          <div className="space-y-4">
            {renderSectionHeader(7, "Additional Information")}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Benefit-Risk Summary *</label>
              <textarea
                value={formData.benefitRiskSummary}
                onChange={(e) => handleInputChange('benefitRiskSummary', e.target.value)}
                rows={3}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Summarize the benefits and potential risks of using this model..."
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Ethical Considerations</label>
              <textarea
                value={formData.ethicalConsiderations}
                onChange={(e) => handleInputChange('ethicalConsiderations', e.target.value)}
                rows={2}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Ethical considerations, privacy, bias mitigation..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Caveats & Limitations *</label>
              <textarea
                value={formData.caveatsLimitations}
                onChange={(e) => handleInputChange('caveatsLimitations', e.target.value)}
                rows={3}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Known limitations, edge cases, scenarios where model may not perform well..."
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Recommendations for Safe Use *</label>
              <textarea
                value={formData.recommendationsSafeUse}
                onChange={(e) => handleInputChange('recommendationsSafeUse', e.target.value)}
                rows={3}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Best practices, monitoring requirements, update frequency..."
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Post-Market Surveillance Plan</label>
              <textarea
                value={formData.postMarketSurveillancePlan}
                onChange={(e) => handleInputChange('postMarketSurveillancePlan', e.target.value)}
                rows={3}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Monitoring cadence, drift triggers, revalidation thresholds."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Explainability Recommendations</label>
              <textarea
                value={formData.explainabilityRecommendations}
                onChange={(e) => handleInputChange('explainabilityRecommendations', e.target.value)}
                rows={2}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="How clinicians should consume model outputs in practice."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Supporting Documents</label>
              <textarea
                value={formData.supportingDocuments}
                onChange={(e) => handleInputChange('supportingDocuments', e.target.value)}
                rows={3}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm"
                placeholder="One URL or reference per line."
              />
              <p className="text-xs text-gray-500 mt-1">Validation reports, supplements, regulatory letters. One per line.</p>
            </div>
          </div>
        );

      default:
        return <div>Section not found</div>;
    }
  };

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <Link href="/" className="text-blue-600 hover:text-blue-800 flex items-center mb-4">
            Back to Dashboard
          </Link>
          <h1 className="text-3xl font-bold text-gray-900">
            {revising ? `Revise card #${revising}` : 'Create Model Card'}
          </h1>
          <p className="text-gray-600 mt-2">
            {revising
              ? `Editing the existing token "${originalModelName}" - same NFT, updated metadata. The reviewer requested changes; describe what you've fixed below.`
              : 'Fill out all 7 sections using the smart-model-card framework'}
          </p>
          {revising && (
            <div className="mt-4 bg-amber-50 border border-amber-200 rounded-lg p-4">
              <label className="block text-sm font-semibold text-amber-900 mb-1">
                Revision notes <span className="text-red-600">*</span>
              </label>
              <textarea
                value={revisionNotes}
                onChange={(e) => setRevisionNotes(e.target.value)}
                placeholder="What did you change? (e.g. 'Clarified intended-use environment per reviewer feedback; added caveat about pediatric populations.')"
                rows={3}
                className="w-full px-3 py-2 border border-amber-300 rounded-md text-sm bg-white"
                required
              />
              <p className="text-xs text-amber-700 mt-1">
                Required. Recorded on chain as part of this revision's audit
                trail. The token ID, version chain, and lineage all stay
                pinned to the same NFT.
              </p>
            </div>
          )}
        </div>

        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Creation Mode</h3>
          <div className="flex gap-4">
            <button
              onClick={() => setCreateMode('new')}
              className={`flex-1 px-6 py-4 rounded-lg border-2 transition ${
                createMode === 'new'
                  ? 'border-blue-600 bg-blue-50 text-blue-900'
                  : 'border-gray-300 bg-white text-gray-700 hover:border-gray-400'
              }`}
            >
              
              <div className="font-semibold mb-1">Create New Model Card</div>
              <div className="text-sm opacity-80">Start from scratch with version 1.0.0</div>
            </button>

            <button
              onClick={() => setCreateMode('version')}
              className={`flex-1 px-6 py-4 rounded-lg border-2 transition ${
                createMode === 'version'
                  ? 'border-purple-600 bg-purple-50 text-purple-900'
                  : 'border-gray-300 bg-white text-gray-700 hover:border-gray-400'
              }`}
            >
              
              <div className="font-semibold mb-1">Create New Version</div>
              <div className="text-sm opacity-80">Supersede an archived model card</div>
            </button>
          </div>

          {createMode === 'version' && (
            <div className="mt-4 p-4 bg-purple-50 border border-purple-200 rounded-lg">
              <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                <div className="flex items-start gap-2">
                  <span className="text-amber-600 text-xs font-semibold uppercase tracking-wide">Warning</span>
                  <div>
                    <h4 className="font-semibold text-amber-900 text-sm">Versioning Requirements</h4>
                    <p className="text-xs text-amber-800 mt-1">
                      Only <strong>archived</strong> model cards can have new versions created.
                      A model card must complete its full lifecycle before being archived:
                    </p>
                    <ol className="text-xs text-amber-700 mt-2 ml-4 list-decimal space-y-0.5">
                      <li>Draft, then Submit for Review</li>
                      <li>Under Review, then Endorse (by Reviewer)</li>
                      <li>Reviewed, then Publish</li>
                      <li>Published, then Archive (with reason)</li>
                      <li>Archived, then Create New Version</li>
                    </ol>
                  </div>
                </div>
              </div>

              <label className="block text-sm font-medium text-purple-900 mb-2">
                Select Archived Model to Supersede *
              </label>
              {existingModels.length === 0 ? (
                <div className="p-4 bg-gray-100 border border-gray-300 rounded-lg text-center">
                  <p className="text-sm text-gray-600 font-medium">No archived models available</p>
                  <p className="text-xs text-gray-500 mt-1">
                    You need to archive an existing published model card before you can create a new version.
                  </p>
                </div>
              ) : (
                <>
                  <select
                    value={selectedParentModel}
                    onChange={(e) => setSelectedParentModel(e.target.value)}
                    className="w-full px-4 py-2 border border-purple-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                    required
                  >
                    <option value="">-- Select an archived model --</option>
                    {existingModels.map((model) => (
                      <option key={model.token_id} value={model.model_name}>
                        {model.model_name} by {model.developer_organization} (v{model.version} - Archived)
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-purple-700 mt-2">
                    A new major version will be created automatically (e.g., v{existingModels.find(m => m.model_name === selectedParentModel)?.version || '1.0.0'} to v2.0.0).
                    The new version will supersede the archived model.
                  </p>
                </>
              )}
            </div>
          )}
        </div>

        {createMode === 'new' && (
          <div className="surface p-6 mb-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">

                <div>
                  <p className="meta">Example</p>
                  <h3 className="text-lg font-semibold tracking-tight mt-1">COPD Exacerbation Risk Predictor</h3>
                  <p className="mt-1 text-[13.5px]" style={{ color: 'var(--fg-muted)' }}>
                    Load the case study from the SMART paper with all fields pre-filled for demonstration
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                {useExample ? (
                  <button
                    onClick={clearExample}
                    className="px-6 py-2.5 bg-white border-2 border-red-300 text-red-700 rounded-lg hover:bg-red-50 transition font-medium flex items-center gap-2"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                    Clear Example
                  </button>
                ) : (
                  <button
                    onClick={populateWithExample}
                    className="px-6 py-2.5 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition font-medium flex items-center gap-2"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    Load Example
                  </button>
                )}
              </div>
            </div>
            {useExample && (
              <div className="mt-4 p-3 bg-emerald-100 rounded-lg border border-emerald-300">
                <div className="flex items-start gap-2">
                  <svg className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <div className="text-sm text-emerald-800">
                    <strong>COPD Example Loaded.</strong> All form fields have been populated with the COPD Exacerbation Risk Predictor case study from the SMART paper, including claimed metrics (AUROC 0.78, Brier 0.14, ECE 0.03). You can edit any field before submitting.
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Progress: Section {currentSection} of 7</h2>
            <span className="text-sm text-gray-600">{Math.round((currentSection / 7) * 100)}% Complete</span>
          </div>

          <div className="w-full bg-gray-200 rounded-full h-2 mb-4">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${(currentSection / 7) * 100}%` }}
            />
          </div>

          <div className="grid grid-cols-7 gap-2">
            {sections.map((section) => (
              <button
                key={section.num}
                onClick={() => setCurrentSection(section.num)}
                className={`p-3 rounded-lg text-center transition relative ${
                  currentSection === section.num
                    ? 'bg-blue-600 text-white shadow-md'
                    : sectionErrors[section.num]?.length > 0
                    ? 'bg-red-50 text-red-700 border-2 border-red-300 hover:bg-red-100'
                    : sectionSaved[section.num]
                    ? 'bg-green-50 text-green-700 border-2 border-green-300'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                <div className="meta mb-1">{String(section.num).padStart(2, '0')}</div>
                <div className="text-xs font-medium">{section.num}</div>
                {sectionErrors[section.num]?.length > 0 && currentSection !== section.num && (
                  <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full flex items-center justify-center">
                    <span className="text-white text-xs font-bold">!</span>
                  </span>
                )}
                {sectionSaved[section.num] && !sectionErrors[section.num]?.length && currentSection !== section.num && (
                  <span className="absolute -top-1 -right-1 w-4 h-4 bg-green-500 rounded-full flex items-center justify-center">
                    <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm p-8 mb-6">
          {renderSectionContent()}
        </div>

        <div className="flex justify-between items-center bg-white rounded-lg shadow-sm p-6">
          <button
            onClick={() => setCurrentSection(Math.max(1, currentSection - 1))}
            disabled={currentSection === 1}
            className={`px-6 py-3 rounded-lg font-medium transition ${
              currentSection === 1
                ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            Previous
          </button>

          <div className="text-sm text-gray-600">
            Section {currentSection} of 7
          </div>

          {currentSection < 7 ? (
            <button
              onClick={() => setCurrentSection(Math.min(7, currentSection + 1))}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition"
            >
              Next
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={loading}
              className={`px-8 py-3 rounded-lg font-medium transition ${
                loading
                  ? 'bg-gray-400 text-white cursor-not-allowed'
                  : 'bg-green-600 text-white hover:bg-green-700'
              }`}
            >
              {loading
                ? (revising ? 'Submitting revision...' : 'Creating...')
                : (revising ? 'Submit revision' : 'Create Model Card')}
            </button>
          )}
        </div>

        {error && currentSection === 7 && !success && (
          <div
            className="mt-4 rounded-lg border p-4 flex items-start justify-between gap-3"
            style={{
              background: 'rgba(185,28,28,0.06)',
              borderColor: 'rgba(185,28,28,0.3)',
              color: 'var(--danger, #b91c1c)',
            }}
          >
            <div className="text-[14px] leading-snug min-w-0">
              <p className="font-medium mb-0.5">Could not create model card</p>
              <p className="opacity-90 break-words">{error}</p>
            </div>
            <button
              onClick={() => setError('')}
              className="text-[12.5px] underline shrink-0"
              style={{ color: 'inherit' }}
            >
              Dismiss
            </button>
          </div>
        )}

        {success && (
          <div className="mt-6 bg-green-50 border border-green-200 rounded-lg p-6 text-center">
            <h3 className="text-xl font-semibold text-green-900 mb-2">
              {revising
                ? `Revision submitted for card #${revising}`
                : 'Model Card Created Successfully!'}
            </h3>
            <p className="text-green-700">
              {revising
                ? 'Same NFT, updated metadata. Redirecting to the card…'
                : 'Redirecting to Tasks - submit it for review from there.'}
            </p>
          </div>
        )}
      </div>
    </main>
  );
}

interface LineagePreviewPanelProps {
  modelName: string;
  creator: string;
  relation: number;
  setRelation: (v: number) => void;
  envelopeText: string;
  setEnvelopeText: (v: string) => void;
}

interface LineagePreview {
  ok: boolean;
  status?: number;
  detail?: string;
  line_name?: string;
  is_root?: boolean;
  next_version_index?: number;
  envelope_pinned?: boolean;
  supersedes?: number;
}

const RELATION_LABELS: Record<number, string> = {
  0: 'Patch (no behaviour change)',
  1: 'Recalibration (decision boundary unchanged)',
  2: 'Retrain (new training data, same architecture)',
  3: 'Reformulation (architecture or feature change)',
  4: 'Reindication (new clinical use)',
  5: 'Withdrawal (no longer recommended)',
};

function LineagePreviewPanel({
  modelName,
  creator,
  relation,
  setRelation,
  envelopeText,
  setEnvelopeText,
}: LineagePreviewPanelProps) {
  const [preview, setPreview] = useState<LineagePreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  useEffect(() => {
    if (!modelName.trim() || !creator) {
      setPreview(null);
      return;
    }
    const handle = setTimeout(async () => {
      setLoading(true);
      try {
        const url = `http://localhost:8000/api/smart-model-card/lineage-preview?model_name=${encodeURIComponent(
          modelName,
        )}&creator=${encodeURIComponent(creator)}&mode=new`;
        const r = await fetch(url);
        const d = await r.json();
        setPreview(d);
      } catch {
        setPreview({ ok: false, detail: 'Could not preview lineage' });
      } finally {
        setLoading(false);
      }
    }, 350);
    return () => clearTimeout(handle);
  }, [modelName, creator]);

  return (
    <div className="mt-8 p-5 border border-gray-300 rounded-lg bg-gray-50">
      <h4 className="text-base font-semibold text-gray-900 mb-1">Lineage</h4>
      <p className="text-xs text-gray-500 mb-3">
        Every model card belongs to a "line" - the long-lived identity of the model
        across versions. The first card under a name claims the line forever; later cards
        are appended as v2, v3… with the transition type (Patch / Retrain / etc.) linking
        each version to its predecessor. The system reads the contracts and figures this
        out from your Model Name - you don't need to fill anything in.
      </p>

      {!modelName.trim() ? (
        <p className="text-sm text-gray-500">Enter a Model Name above to see what will be recorded.</p>
      ) : loading ? (
        <p className="text-sm text-gray-500">Resolving on-chain state…</p>
      ) : preview && !preview.ok ? (
        <div className="rounded-md border p-3" style={{ background: 'rgba(185,28,28,0.06)', borderColor: 'rgba(185,28,28,0.3)' }}>
          <p className="text-sm font-medium" style={{ color: 'var(--danger,#b91c1c)' }}>{preview.detail}</p>
        </div>
      ) : preview ? (
        <div className="rounded-md border border-gray-200 bg-white p-3">
          <p className="text-sm">
            {preview.is_root ? (
              <>
                <span className="font-medium">First version</span> of new line{' '}
                <span className="font-mono text-blue-700">{preview.line_name}</span>
              </>
            ) : (
              <>
                <span className="font-medium">Version {preview.next_version_index}</span> of{' '}
                <span className="font-mono text-blue-700">{preview.line_name}</span>{' '}
                <span className="text-gray-500">(supersedes token #{preview.supersedes})</span>
              </>
            )}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            Transition: <span className="font-medium text-gray-700">{RELATION_LABELS[relation] || RELATION_LABELS[0]}</span>
            {preview.envelope_pinned ? ' · envelope present on this line' : ''}
          </p>
        </div>
      ) : null}

      <div className="mt-3">
        <button
          type="button"
          onClick={() => setAdvancedOpen((v) => !v)}
          className="text-xs text-gray-500 hover:text-gray-700 underline"
        >
          {advancedOpen ? 'Hide advanced' : 'Advanced (override transition / pin envelope)'}
        </button>
      </div>

      {advancedOpen && (
        <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Transition type</label>
            <select
              value={relation}
              onChange={(e) => setRelation(Number(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              {Object.entries(RELATION_LABELS).map(([v, label]) => (
                <option key={v} value={v}>{label}</option>
              ))}
            </select>
            <p className="text-xs text-gray-500 mt-1">
              Defaults to Patch. Change only if this version represents a meaningful behaviour shift.
            </p>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Predetermined-change envelope (only for new lines)
            </label>
            <textarea
              value={envelopeText}
              onChange={(e) => setEnvelopeText(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-xs font-mono"
              placeholder="Free text describing allowed future changes (e.g. monthly recalibration on rolling 12-month window). Hashed and pinned to the line."
            />
            <p className="text-xs text-gray-500 mt-1">
              Optional. Leave blank to skip - you can pin one later if regulatory needs change.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

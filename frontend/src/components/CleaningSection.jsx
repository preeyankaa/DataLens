import { useState, useEffect, useRef } from "react";
import {
  WandSparkles,
  Download,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Plus,
  X,
  Save,
  Upload,
  Code2,
  Undo2,
  Copy,
  FileSpreadsheet,
} from "lucide-react";
import "./CleaningSteps.css";

const API_URL = "http://127.0.0.1:8000";

/* ---------- column helpers ----------
   The backend now sends `inferred_type` (numeric, categorical, date, id,
   text, boolean) worked out from the data itself. When it is missing, the
   older name/type guesses are used. */

const normalizeName = (name) =>
  String(name).toLowerCase().replace(/[^a-z0-9]+/g, "_");

const isNumericColumn = (details = {}) => {
  if (details.inferred_type) return details.inferred_type === "numeric";

  return ["int64", "float64", "int", "float", "number"].includes(
    String(details.data_type).toLowerCase()
  );
};

const isIdentifierColumn = (name, details = {}) => {
  if (details.inferred_type) return details.inferred_type === "id";

  const normalized = normalizeName(name);
  const tokens = normalized.split("_");

  return (
    tokens.includes("id") ||
    tokens.includes("uuid") ||
    tokens.includes("identifier") ||
    tokens.includes("reference") ||
    normalized.endsWith("_key")
  );
};

const isDateColumn = (name, details = {}) => {
  if (details.inferred_type) return details.inferred_type === "date";

  const normalized = normalizeName(name);
  const dataType = String(details.data_type || "").toLowerCase();

  return (
    normalized.includes("date") ||
    normalized.includes("timestamp") ||
    normalized.includes("time") ||
    dataType.includes("datetime")
  );
};

const isReturnColumn = (name) =>
  ["returned", "is_returned", "return_status"].includes(normalizeName(name));

const isTotalColumn = (name) =>
  ["line_total", "total", "revenue", "sales_amount"].includes(
    normalizeName(name)
  );

const isDiscountColumn = (name) => normalizeName(name).includes("discount");

const getDefaultStrategy = (name, details) => {
  if (isReturnColumn(name) || isIdentifierColumn(name, details)) return "skip";
  if (isDateColumn(name, details)) return "drop_rows";
  if (isTotalColumn(name)) return "skip";
  // An empty discount almost always means "no discount".
  if (isDiscountColumn(name) && isNumericColumn(details)) return "zero";
  if (isNumericColumn(details)) return "median";

  return "unknown";
};

const createInitialMissingSelection = (columns) => {
  const initial = {};

  Object.entries(columns).forEach(([name, details]) => {
    if (details.missing_count > 0) {
      initial[name] = {
        enabled: true,
        strategy: getDefaultStrategy(name, details),
      };
    }
  });

  return initial;
};

const getInconsistentColumns = (qualityReport) =>
  (qualityReport?.issues || [])
    .filter((issue) => issue.type === "inconsistent_text" && issue.column)
    .map((issue) => ({
      column: issue.column,
      count: issue.count,
      example: (issue.examples?.[0] || []).join("  /  "),
    }));

/* ---------- custom steps ---------- */

const STEP_TYPES = [
  { value: "rename", label: "Rename a column" },
  { value: "drop_column", label: "Remove a column" },
  { value: "find_replace", label: "Find and replace text" },
  { value: "text_case", label: "Change capital letters" },
  { value: "drop_rows", label: "Remove rows that match a rule" },
  { value: "to_number", label: "Turn text into numbers" },
];

const ROW_OPERATORS = [
  { value: "<", label: "is less than" },
  { value: "<=", label: "is at most" },
  { value: ">", label: "is more than" },
  { value: ">=", label: "is at least" },
  { value: "==", label: "is equal to" },
  { value: "!=", label: "is not equal to" },
  { value: "contains", label: "contains" },
  { value: "is_null", label: "is empty" },
  { value: "not_null", label: "is not empty" },
];

const NO_VALUE_OPERATORS = ["is_null", "not_null"];

const STRATEGY_LABELS = {
  median: "fill with the median",
  mean: "fill with the average",
  mode: "fill with the most common value",
  zero: "fill with 0",
  unknown: "label as (Unknown)",
  drop_rows: "remove those rows",
};

const EMPTY_DRAFT = {
  column: "",
  newName: "",
  find: "",
  replace: "",
  match: "exact",
  caseSensitive: false,
  mode: "lower",
  op: "<",
  value: "",
};

const describeStep = (step) => {
  switch (step.type) {
    case "rename":
      return `Rename "${step.column}" to "${step.newName}"`;
    case "drop_column":
      return `Remove the column "${step.column}"`;
    case "find_replace":
      return `In "${step.column}", ${
        step.match === "contains" ? "replace text containing" : "replace"
      } "${step.find}" with ${step.replace === "" ? "an empty cell" : `"${step.replace}"`}`;
    case "text_case":
      return `Write "${step.column}" in ${step.mode} case`;
    case "drop_rows": {
      const label = ROW_OPERATORS.find((o) => o.value === step.op)?.label || step.op;
      return NO_VALUE_OPERATORS.includes(step.op)
        ? `Remove rows where "${step.column}" ${label}`
        : `Remove rows where "${step.column}" ${label} ${step.value}`;
    }
    case "to_number":
      return `Turn "${step.column}" into numbers (removes $, commas and spaces)`;
    default:
      return step.type;
  }
};

const formatChange = (value) => {
  if (value === null || value === undefined) return "-";
  if (typeof value !== "object") return String(value);

  return Object.entries(value)
    .filter(([key]) => key !== "examples")
    .map(([key, val]) => {
      const text = typeof val === "object" && val !== null ? JSON.stringify(val) : val;
      return `${key.replaceAll("_", " ")}: ${text}`;
    })
    .join(" · ");
};

const downloadText = (text, filename, type) => {
  const blob = new Blob([text], { type });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

const ALLOWED_STRATEGIES = [
  "median", "mean", "mode", "zero", "unknown", "skip", "drop_rows",
];

function CleaningSection({ datasetId, profile, qualityReport }) {
  const columns = profile?.columns || {};
  const statistics = profile?.numerical_statistics || {};

  const missingColumns = Object.entries(columns).filter(
    ([, details]) => details.missing_count > 0
  );

  const numericalColumns = Object.keys(statistics).filter(
    (name) => !isIdentifierColumn(name, columns[name])
  );

  const dateColumns = Object.entries(columns)
    .filter(([name, details]) => isDateColumn(name, details))
    .map(([name]) => name);

  const inconsistentColumns = getInconsistentColumns(qualityReport);

  const mixedDateColumns = (qualityReport?.issues || [])
    .filter((issue) => issue.type === "mixed_date_formats")
    .map((issue) => issue.column);

  const profileSignature = Object.entries(columns)
    .map(([name, details]) =>
      `${name}:${details.missing_count}:${details.data_type}`
    )
    .join("|");

  const inconsistentSignature = inconsistentColumns
    .map((item) => `${item.column}:${item.count}`)
    .join("|");

  const [removeDuplicates, setRemoveDuplicates] = useState(true);

  const [selectedMissing, setSelectedMissing] = useState(() =>
    createInitialMissingSelection(columns)
  );

  const [selectedOutliers, setSelectedOutliers] = useState([]);

  const [selectedCase, setSelectedCase] = useState(() =>
    inconsistentColumns.map((item) => item.column)
  );

  const [datesOn, setDatesOn] = useState(true);
  const [customSteps, setCustomSteps] = useState([]);
  const [draftType, setDraftType] = useState("");
  const [draft, setDraft] = useState(EMPTY_DRAFT);
  const [draftError, setDraftError] = useState("");

  const [hasApplied, setHasApplied] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [notice, setNotice] = useState("");
  const [code, setCode] = useState("");
  const [codeLoading, setCodeLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const recipeInputRef = useRef(null);
  const stepCounter = useRef(0);

  const [preview, setPreview] = useState(null);
  const [previewPayload, setPreviewPayload] = useState(null);

  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const [cleanedReady, setCleanedReady] = useState(false);

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    setSelectedMissing(createInitialMissingSelection(columns));
    setSelectedOutliers([]);
    setSelectedCase(inconsistentColumns.map((item) => item.column));
    setRemoveDuplicates(true);
    setDatesOn(true);
    setCustomSteps([]);
    setDraftType("");
    setNotice("");
    setCode("");

    setPreview(null);
    setPreviewPayload(null);
    setCleanedReady(false);
    setSuccess("");
    setError("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId, profileSignature, inconsistentSignature]);

  const buildPayload = () => {
    const missingValues = {};

    Object.entries(selectedMissing).forEach(([name, settings]) => {
      if (!settings.enabled) return;

      // "zero" is shown to the user as "Fill with 0"
      missingValues[name] =
        settings.strategy === "zero"
          ? { strategy: "constant", value: 0 }
          : { strategy: settings.strategy };
    });

    const payload = {
      remove_duplicates: removeDuplicates,
      merge_case_columns: selectedCase,
      missing_values: missingValues,
      date_columns: datesOn ? dateColumns : [],
      outlier_columns: selectedOutliers,
    };

    const renames = {};
    const drops = [];
    const replaces = [];
    const cases = {};
    const rules = [];
    const types = {};

    customSteps.forEach((step) => {
      if (step.type === "rename") renames[step.column] = step.newName.trim();
      if (step.type === "drop_column") drops.push(step.column);
      if (step.type === "find_replace") {
        replaces.push({
          column: step.column,
          find: step.find,
          replace: step.replace,
          match: step.match,
          case_sensitive: step.caseSensitive,
        });
      }
      if (step.type === "text_case") cases[step.column] = step.mode;
      if (step.type === "drop_rows") {
        rules.push({
          column: step.column,
          op: step.op,
          ...(NO_VALUE_OPERATORS.includes(step.op) ? {} : { value: step.value }),
        });
      }
      if (step.type === "to_number") types[step.column] = "float";
    });

    if (Object.keys(renames).length) payload.rename_columns = renames;
    if (drops.length) payload.drop_columns = drops;
    if (replaces.length) payload.find_replace = replaces;
    if (Object.keys(cases).length) payload.text_case = cases;
    if (rules.length) payload.drop_rows = rules;
    if (Object.keys(types).length) payload.type_conversions = types;

    return payload;
  };

  const resetCleaningStatus = () => {
    setPreview(null);
    setPreviewPayload(null);
    setCleanedReady(false);
    setSuccess("");
    setError("");
  };

  const handleMissingToggle = (name) => {
    setSelectedMissing((current) => ({
      ...current,
      [name]: {
        ...current[name],
        enabled: !current[name].enabled,
      },
    }));

    resetCleaningStatus();
  };

  const handleStrategyChange = (name, strategy) => {
    setSelectedMissing((current) => ({
      ...current,
      [name]: {
        ...current[name],
        strategy,
      },
    }));

    resetCleaningStatus();
  };

  const handleOutlierToggle = (name) => {
    setSelectedOutliers((current) =>
      current.includes(name)
        ? current.filter((item) => item !== name)
        : [...current, name]
    );

    resetCleaningStatus();
  };

  const handleCaseToggle = (name) => {
    setSelectedCase((current) =>
      current.includes(name)
        ? current.filter((item) => item !== name)
        : [...current, name]
    );

    resetCleaningStatus();
  };

  /* ----- custom steps ----- */

  const allColumnNames = Object.keys(columns);
  const textColumnNames = allColumnNames.filter(
    (name) => !isNumericColumn(columns[name])
  );

  const columnChoices = (type) =>
    type === "find_replace" || type === "text_case" || type === "to_number"
      ? textColumnNames
      : allColumnNames;

  const startDraft = (type) => {
    setDraftType(type);
    setDraft({ ...EMPTY_DRAFT, column: columnChoices(type)[0] || "" });
    setDraftError("");
  };

  const updateDraft = (patch) => setDraft((current) => ({ ...current, ...patch }));

  const validateDraft = () => {
    if (!draft.column) return "Choose a column.";

    if (draftType === "rename") {
      const name = draft.newName.trim();
      if (!name) return "Type the new name.";

      const takenByOthers = allColumnNames.some(
        (c) => c !== draft.column && c === name
      );
      const takenByStep = customSteps.some(
        (st) => st.type === "rename" && st.column !== draft.column && st.newName.trim() === name
      );
      if (takenByOthers || takenByStep) return `A column called "${name}" already exists.`;
    }

    if (draftType === "find_replace" && draft.find === "") {
      return "Type the text to look for.";
    }

    if (
      draftType === "drop_rows" &&
      !NO_VALUE_OPERATORS.includes(draft.op) &&
      String(draft.value).trim() === ""
    ) {
      return "Type a value for the rule.";
    }

    return "";
  };

  const addStep = () => {
    const problem = validateDraft();
    if (problem) {
      setDraftError(problem);
      return;
    }

    stepCounter.current += 1;

    setCustomSteps((current) => {
      // one rename / case rule per column: the newest replaces the older one
      const kept = current.filter(
        (st) =>
          !(
            st.column === draft.column &&
            st.type === draftType &&
            ["rename", "text_case", "drop_column", "to_number"].includes(st.type)
          )
      );
      return [...kept, { id: `step-${stepCounter.current}`, type: draftType, ...draft }];
    });

    setDraftType("");
    setDraftError("");
    resetCleaningStatus();
  };

  const removeStep = (id) => {
    setCustomSteps((current) => current.filter((st) => st.id !== id));
    resetCleaningStatus();
  };

  /* ----- recipe (save / load) ----- */

  const handleSaveRecipe = () => {
    const recipe = {
      type: "datalens-recipe",
      version: 1,
      created: new Date().toISOString(),
      operations: buildPayload(),
    };

    downloadText(
      JSON.stringify(recipe, null, 2),
      "datalens-recipe.json",
      "application/json"
    );
  };

  const applyRecipe = (operations) => {
    const known = new Set(allColumnNames);
    const skipped = new Set();

    const keep = (name) => {
      if (known.has(name)) return true;
      skipped.add(name);
      return false;
    };

    setRemoveDuplicates(Boolean(operations.remove_duplicates));
    setSelectedCase((operations.merge_case_columns || []).filter(keep));
    setSelectedOutliers((operations.outlier_columns || []).filter(keep));
    setDatesOn((operations.date_columns || []).length > 0);

    const missing = {};
    Object.entries(columns).forEach(([name, details]) => {
      if (details.missing_count > 0) {
        missing[name] = { enabled: false, strategy: getDefaultStrategy(name, details) };
      }
    });

    Object.entries(operations.missing_values || {}).forEach(([name, config]) => {
      if (!keep(name) || !missing[name]) return;

      let strategy = config?.strategy;
      if (strategy === "constant" && Number(config.value) === 0) strategy = "zero";
      if (!ALLOWED_STRATEGIES.includes(strategy)) {
        strategy = getDefaultStrategy(name, columns[name]);
      }

      missing[name] = { enabled: true, strategy };
    });

    setSelectedMissing(missing);

    const steps = [];
    const add = (step) => {
      stepCounter.current += 1;
      steps.push({ ...EMPTY_DRAFT, id: `step-${stepCounter.current}`, ...step });
    };

    Object.entries(operations.rename_columns || {}).forEach(([column, newName]) => {
      if (keep(column)) add({ type: "rename", column, newName });
    });
    (operations.drop_columns || []).forEach((column) => {
      if (keep(column)) add({ type: "drop_column", column });
    });
    (operations.find_replace || []).forEach((rule) => {
      if (keep(rule.column)) {
        add({
          type: "find_replace",
          column: rule.column,
          find: rule.find ?? "",
          replace: rule.replace ?? "",
          match: rule.match || "exact",
          caseSensitive: Boolean(rule.case_sensitive),
        });
      }
    });
    Object.entries(operations.text_case || {}).forEach(([column, mode]) => {
      if (keep(column)) add({ type: "text_case", column, mode });
    });
    (operations.drop_rows || []).forEach((rule) => {
      if (keep(rule.column)) {
        add({ type: "drop_rows", column: rule.column, op: rule.op, value: rule.value ?? "" });
      }
    });
    Object.entries(operations.type_conversions || {}).forEach(([column, target]) => {
      if (target === "float" && keep(column)) add({ type: "to_number", column });
    });

    setCustomSteps(steps);
    resetCleaningStatus();

    setNotice(
      skipped.size > 0
        ? `Recipe loaded. ${skipped.size} column(s) from the recipe are not in this file and were skipped: ${[...skipped].join(", ")}.`
        : "Recipe loaded. Review the steps on the right, then preview the changes."
    );
  };

  const handleRecipeFile = (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    const reader = new FileReader();

    reader.onload = () => {
      try {
        const recipe = JSON.parse(String(reader.result));

        if (recipe?.type !== "datalens-recipe" || typeof recipe.operations !== "object") {
          throw new Error("not a recipe");
        }

        applyRecipe(recipe.operations);
      } catch {
        setError("This file is not a DataLens recipe.");
      }
    };

    reader.readAsText(file);
  };

  /* ----- python export and start over ----- */

  const handleShowCode = async () => {
    setCodeLoading(true);
    setError("");
    setCopied(false);

    try {
      const response = await fetch(
        `${API_URL}/api/v1/datasets/${datasetId}/clean/code`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(buildPayload()),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string" ? data.detail : "Could not create the code."
        );
      }

      setCode(data.code);
    } catch (err) {
      setError(err.message || "Could not create the code.");
    } finally {
      setCodeLoading(false);
    }
  };

  const handleCopyCode = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
    } catch {
      setError("Could not copy. Use Download instead.");
    }
  };

  const handleStartOver = async () => {
    setError("");
    setSuccess("");

    try {
      const response = await fetch(`${API_URL}/api/v1/datasets/${datasetId}/clean`, {
        method: "DELETE",
      });

      if (!response.ok) throw new Error("Could not remove the cleaning.");

      setHasApplied(false);
      setCleanedReady(false);
      setPreview(null);
      setPreviewPayload(null);
      setSuccess(
        "Cleaning removed. Charts and AI questions now use your original data."
      );
    } catch (err) {
      setError(err.message || "Something went wrong.");
    }
  };

  // Is a cleaned version already saved on the server?
  useEffect(() => {
    let alive = true;

    fetch(`${API_URL}/api/v1/datasets/${datasetId}/clean/report`)
      .then((response) => response.json())
      .then((data) => alive && setHasApplied(Boolean(data.available)))
      .catch(() => {});

    return () => {
      alive = false;
    };
  }, [datasetId]);

  const handlePreview = async () => {
    setLoading(true);
    setError("");
    setSuccess("");
    setPreview(null);
    setPreviewPayload(null);
    setCleanedReady(false);

    try {
      // Save the exact settings used for this preview.
      const payload = buildPayload();

      const response = await fetch(
        `${API_URL}/api/v1/datasets/${datasetId}/clean/preview`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "Could not generate cleaning preview."
        );
      }

      setPreview(data);
      setPreviewPayload(payload);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const handleApplyCleaning = async () => {
    if (!preview || !previewPayload) {
      setError("Please generate a preview before applying cleaning.");
      return;
    }

    setApplying(true);
    setError("");
    setSuccess("");

    try {
      const response = await fetch(
        `${API_URL}/api/v1/datasets/${datasetId}/clean/apply`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(previewPayload),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "Could not apply cleaning."
        );
      }

      setCleanedReady(true);
      setHasApplied(true);

      setSuccess(
        "Cleaning applied successfully. Your cleaned dataset is ready for charts and AI questions."
      );
    } catch (err) {
      setError(err.message || "Could not apply cleaning.");
    } finally {
      setApplying(false);
    }
  };

  const handleDownload = async () => {
    if (!cleanedReady || !previewPayload) {
      setError("Please apply cleaning before downloading the cleaned CSV.");
      return;
    }

    setDownloading(true);
    setError("");
    setSuccess("");

    try {
      const response = await fetch(
        `${API_URL}/api/v1/datasets/${datasetId}/clean/download`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(previewPayload),
        }
      );

      if (!response.ok) {
        let message = "Could not download the cleaned dataset.";

        try {
          const data = await response.json();

          if (typeof data.detail === "string") {
            message = data.detail;
          }
        } catch {
          // Keep default error message.
        }

        throw new Error(message);
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");

      link.href = url;
      link.download = "datalens-cleaned.csv";

      document.body.appendChild(link);
      link.click();
      link.remove();

      window.URL.revokeObjectURL(url);

      setSuccess("Your cleaned CSV has been downloaded.");
    } catch (err) {
      setError(err.message || "Download failed.");
    } finally {
      setDownloading(false);
    }
  };

  const handleExportExcel = async () => {
    setExporting(true);
    setError("");
    setSuccess("");

    try {
      const response = await fetch(
        `${API_URL}/api/v1/datasets/${datasetId}/export?format=xlsx`
      );

      if (!response.ok) {
        let message = "Could not create the Excel file.";

        try {
          const data = await response.json();
          if (typeof data.detail === "string") message = data.detail;
        } catch {
          // keep the default message
        }

        throw new Error(message);
      }

      const disposition = response.headers.get("Content-Disposition") || "";
      const match = /filename="([^"]+)"/.exec(disposition);

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");

      link.href = url;
      link.download = match?.[1] || "datalens-cleaned.xlsx";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      setSuccess(
        "Excel file downloaded. It has your cleaned data plus a sheet listing every change."
      );
    } catch (err) {
      setError(err.message || "Download failed.");
    } finally {
      setExporting(false);
    }
  };

  const stepList = [];

  if (removeDuplicates) {
    stepList.push({
      key: "dups",
      text: "Remove duplicate rows",
      remove: () => setRemoveDuplicates(false),
    });
  }

  selectedCase.forEach((name) =>
    stepList.push({
      key: `case-${name}`,
      text: `Make spellings in "${name}" consistent`,
      remove: () => handleCaseToggle(name),
    })
  );

  if (datesOn && dateColumns.length > 0) {
    stepList.push({
      key: "dates",
      text: `Write dates in ${dateColumns.join(", ")} as YYYY-MM-DD`,
      remove: () => setDatesOn(false),
    });
  }

  Object.entries(selectedMissing).forEach(([name, settings]) => {
    if (settings.enabled && settings.strategy !== "skip") {
      stepList.push({
        key: `miss-${name}`,
        text: `Empty cells in "${name}": ${STRATEGY_LABELS[settings.strategy] || settings.strategy}`,
        remove: () => handleMissingToggle(name),
      });
    }
  });

  selectedOutliers.forEach((name) =>
    stepList.push({
      key: `out-${name}`,
      text: `Cap extreme values in "${name}"`,
      remove: () => handleOutlierToggle(name),
    })
  );

  customSteps.forEach((step) =>
    stepList.push({
      key: step.id,
      text: describeStep(step),
      remove: () => removeStep(step.id),
    })
  );

  const renderStrategyOptions = (name, details) => {
    if (isReturnColumn(name) || isIdentifierColumn(name, details)) {
      return <option value="skip">Keep missing values</option>;
    }

    if (isTotalColumn(name)) {
      return (
        <>
          <option value="skip">Keep missing values (recommended)</option>
          <option value="median">Median</option>
          <option value="mean">Mean</option>
        </>
      );
    }

    if (isDateColumn(name, details)) {
      return (
        <>
          <option value="drop_rows">Remove rows with missing dates</option>
          <option value="skip">Keep missing values</option>
        </>
      );
    }

    if (isNumericColumn(details)) {
      return (
        <>
          <option value="median">Median</option>
          <option value="mean">Mean</option>
          <option value="mode">Mode</option>
          <option value="zero">Fill with 0</option>
          <option value="skip">Keep missing values</option>
        </>
      );
    }

    return (
      <>
        <option value="unknown">Fill as (Unknown)</option>
        <option value="skip">Keep missing values</option>
        <option value="mode">Mode</option>
      </>
    );
  };

  return (
    <section className="cleaning-section" id="cleaning">
      <div className="cleaning-heading">
        <span className="eyebrow">DATA PREPARATION</span>
        <h2>Clean your dataset</h2>
        <p>
          Choose how you want to handle data quality issues.
          Preview the changes before applying them to your dataset.
        </p>
      </div>

      <div className="cleaning-options">
        <div className="cstep-stack">
        <div className="cleaning-card">
          <div className="cleaning-card-heading">
            <div>
              <h3>Remove duplicate rows</h3>
              <p>
                Remove repeated records. Spellings and dates are made
                consistent first, so near-copies are caught too.
              </p>
            </div>

            <label className="cleaning-toggle">
              <input
                type="checkbox"
                checked={removeDuplicates}
                onChange={(e) => {
                  setRemoveDuplicates(e.target.checked);
                  resetCleaningStatus();
                }}
              />
              <span />
            </label>
          </div>

          <div className="cleaning-divider" />

          <h3>Make spellings consistent</h3>
          <p>
            The same value is written in different ways. Without this, charts
            split one group into several.
          </p>

          {inconsistentColumns.length > 0 ? (
            inconsistentColumns.map((item) => (
              <label className="cleaning-column-label cleaning-case-row" key={item.column}>
                <input
                  type="checkbox"
                  checked={selectedCase.includes(item.column)}
                  onChange={() => handleCaseToggle(item.column)}
                />

                <span>
                  <strong>{item.column}</strong>
                  <small>
                    {item.count} cells differ
                    {item.example ? ` · for example: ${item.example}` : ""}
                  </small>
                </span>
              </label>
            ))
          ) : (
            <p>No inconsistent spellings detected.</p>
          )}

          {dateColumns.length > 0 && (
            <>
              <div className="cleaning-divider" />

              <h3>Dates</h3>
              <p>
                {dateColumns.join(", ")} will be converted to one format
                (YYYY-MM-DD).
                {mixedDateColumns.length > 0 &&
                  ` ${mixedDateColumns.join(", ")} mixes two date styles. The cleaning report shows which dates were ambiguous.`}
              </p>

              <label className="cleaning-checkbox-row">
                <input
                  type="checkbox"
                  checked={datesOn}
                  onChange={(e) => {
                    setDatesOn(e.target.checked);
                    resetCleaningStatus();
                  }}
                />
                <span>Convert these dates</span>
              </label>
            </>
          )}

          <div className="cleaning-divider" />

          <h3>Handle missing values</h3>
          <p>Select columns and choose a filling strategy.</p>

          {missingColumns.length > 0 ? (
            missingColumns.map(([name, details]) => (
              <div className="cleaning-column-row" key={name}>
                <label className="cleaning-column-label">
                  <input
                    type="checkbox"
                    checked={selectedMissing[name]?.enabled ?? false}
                    onChange={() => handleMissingToggle(name)}
                  />

                  <span>
                    <strong>{name}</strong>
                    <small>{details.missing_count} missing values</small>
                  </span>
                </label>

                <select
                  value={selectedMissing[name]?.strategy || "skip"}
                  disabled={!selectedMissing[name]?.enabled}
                  onChange={(e) =>
                    handleStrategyChange(name, e.target.value)
                  }
                >
                  {renderStrategyOptions(name, details)}
                </select>
              </div>
            ))
          ) : (
            <p>No missing values detected.</p>
          )}

          <div className="cleaning-divider" />

          <h3>Handle outliers</h3>
          <p>Choose numerical columns for IQR-based clipping.</p>

          {numericalColumns.length > 0 ? (
            numericalColumns.map((name) => (
              <label className="cleaning-checkbox-row" key={name}>
                <input
                  type="checkbox"
                  checked={selectedOutliers.includes(name)}
                  onChange={() => handleOutlierToggle(name)}
                />
                <span>{name}</span>
              </label>
            ))
          ) : (
            <p>No suitable numerical columns found.</p>
          )}
        </div>

        <div className="cleaning-card">
          <h3>Add your own step</h3>
          <p>
            Rename or remove columns, fix text, or remove rows that break a
            rule. Every step can be undone from the list on the right.
          </p>

          <select
            className="cstep-select"
            value={draftType}
            onChange={(e) =>
              e.target.value ? startDraft(e.target.value) : setDraftType("")
            }
          >
            <option value="">Choose a step...</option>
            {STEP_TYPES.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>

          {draftType && (
            <div className="cstep-form">
              <label>
                <span>Column</span>
                <select
                  value={draft.column}
                  onChange={(e) => updateDraft({ column: e.target.value })}
                >
                  {columnChoices(draftType).map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>

              {draftType === "rename" && (
                <label>
                  <span>New name</span>
                  <input
                    type="text"
                    value={draft.newName}
                    onChange={(e) => updateDraft({ newName: e.target.value })}
                    placeholder="For example: Revenue"
                  />
                </label>
              )}

              {draftType === "find_replace" && (
                <>
                  <label>
                    <span>Look for</span>
                    <select
                      value={draft.match}
                      onChange={(e) => updateDraft({ match: e.target.value })}
                    >
                      <option value="exact">A cell that is exactly...</option>
                      <option value="contains">Text that contains...</option>
                    </select>
                  </label>
                  <label>
                    <span>Text</span>
                    <input
                      type="text"
                      value={draft.find}
                      onChange={(e) => updateDraft({ find: e.target.value })}
                      placeholder='For example: N/A'
                    />
                  </label>
                  <label>
                    <span>Replace with</span>
                    <input
                      type="text"
                      value={draft.replace}
                      onChange={(e) => updateDraft({ replace: e.target.value })}
                      placeholder="Leave empty to make the cell blank"
                    />
                  </label>
                  <label className="cstep-check">
                    <input
                      type="checkbox"
                      checked={draft.caseSensitive}
                      onChange={(e) => updateDraft({ caseSensitive: e.target.checked })}
                    />
                    <span>Match capital letters exactly</span>
                  </label>
                </>
              )}

              {draftType === "text_case" && (
                <label>
                  <span>Write it in</span>
                  <select
                    value={draft.mode}
                    onChange={(e) => updateDraft({ mode: e.target.value })}
                  >
                    <option value="lower">lower case (anna lee)</option>
                    <option value="upper">UPPER CASE (ANNA LEE)</option>
                    <option value="title">Title Case (Anna Lee)</option>
                  </select>
                </label>
              )}

              {draftType === "drop_rows" && (
                <>
                  <label>
                    <span>Remove rows where the value</span>
                    <select
                      value={draft.op}
                      onChange={(e) => updateDraft({ op: e.target.value })}
                    >
                      {ROW_OPERATORS.map((op) => (
                        <option key={op.value} value={op.value}>
                          {op.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  {!NO_VALUE_OPERATORS.includes(draft.op) && (
                    <label>
                      <span>Value</span>
                      <input
                        type="text"
                        value={draft.value}
                        onChange={(e) => updateDraft({ value: e.target.value })}
                        placeholder="For example: 0 or 2025-01-01"
                      />
                    </label>
                  )}
                </>
              )}

              {draftType === "drop_column" && (
                <p className="cstep-hint">
                  The column is removed at the end, so your other steps can
                  still use it.
                </p>
              )}

              {draftType === "to_number" && (
                <p className="cstep-hint">
                  Values like $1,200 or 35 % become numbers. Anything that is
                  not a number becomes an empty cell.
                </p>
              )}

              {draftError && <p className="cstep-error">{draftError}</p>}

              <div className="cstep-form-actions">
                <button type="button" className="cstep-add" onClick={addStep}>
                  <Plus size={15} /> Add step
                </button>
                <button
                  type="button"
                  className="cstep-cancel"
                  onClick={() => setDraftType("")}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
        </div>

        <div className="cleaning-action-card">
          <div className="cleaning-action-icon">
            <WandSparkles size={24} />
          </div>

          <h3>Ready to clean?</h3>
          <p>
            Generate a preview to see how your dataset will change
            with the selected options.
          </p>

          <button
            className="primary-button"
            type="button"
            onClick={handlePreview}
            disabled={loading || applying || downloading || !datasetId}
          >
            {loading ? (
              <>
                <RefreshCw size={17} className="spin-icon" />
                Generating preview...
              </>
            ) : (
              <>
                Preview changes
                <WandSparkles size={17} />
              </>
            )}
          </button>

          <p className="cleaning-note">
            Previewing does not overwrite your original dataset.
          </p>

          <div className="cstep-panel">
            <div className="cstep-panel-head">
              <h4>Your cleaning steps</h4>
              <span>{stepList.length}</span>
            </div>

            {stepList.length > 0 ? (
              <ul className="cstep-list">
                {stepList.map((item) => (
                  <li key={item.key}>
                    <span>{item.text}</span>
                    <button
                      type="button"
                      title="Undo this step"
                      aria-label="Undo this step"
                      onClick={item.remove}
                    >
                      <X size={14} />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="cstep-empty">No steps selected, so nothing will change.</p>
            )}

            <div className="cstep-tools">
              <button type="button" onClick={handleSaveRecipe}>
                <Save size={14} /> Save recipe
              </button>
              <button type="button" onClick={() => recipeInputRef.current?.click()}>
                <Upload size={14} /> Load recipe
              </button>
              <button type="button" onClick={handleShowCode} disabled={codeLoading}>
                <Code2 size={14} /> {codeLoading ? "Creating..." : "Python code"}
              </button>
              {hasApplied && (
                <button type="button" className="cstep-danger" onClick={handleStartOver}>
                  <Undo2 size={14} /> Start over
                </button>
              )}
              <input
                ref={recipeInputRef}
                type="file"
                accept=".json,application/json"
                hidden
                onChange={handleRecipeFile}
              />
            </div>

            <p className="cstep-recipe-note">
              A recipe saves your steps so you can run them on next month's file.
            </p>
          </div>
        </div>
      </div>

      {notice && (
        <div className="cleaning-message cstep-notice">
          <CheckCircle2 size={18} />
          {notice}
        </div>
      )}

      {code && (
        <div className="cstep-code">
          <div className="cstep-code-head">
            <div>
              <h4>Your cleaning as Python code</h4>
              <p>
                Run it yourself with pandas and you get the same result as
                this page.
              </p>
            </div>
            <div className="cstep-code-actions">
              <button type="button" onClick={handleCopyCode}>
                <Copy size={14} /> {copied ? "Copied" : "Copy"}
              </button>
              <button
                type="button"
                onClick={() => downloadText(code, "datalens_cleaning.py", "text/x-python")}
              >
                <Download size={14} /> Download .py
              </button>
              <button type="button" onClick={() => setCode("")}>
                <X size={14} /> Close
              </button>
            </div>
          </div>
          <pre>{code}</pre>
        </div>
      )}

      {error && (
        <div className="cleaning-message error-message">
          <AlertCircle size={18} />
          {error}
        </div>
      )}

      {success && (
        <div className="cleaning-message success-message">
          <CheckCircle2 size={18} />
          {success}
        </div>
      )}

      {preview && (
        <div className="cleaning-preview">
          <div className="cleaning-preview-heading">
            <div>
              <span className="eyebrow">PREVIEW RESULTS</span>
              <h3>Before and after cleaning</h3>
              <p>Review the changes before applying them.</p>
            </div>

            <span className="dataset-status">
              {cleanedReady ? "Cleaning applied" : "Preview ready"}
            </span>
          </div>

          <div className="cleaning-comparison">
            <div className="comparison-card">
              <span>Before</span>
              <strong>{preview.before.rows}</strong>
              <small>Rows</small>
              <p>{preview.before.missing_values} missing values</p>
              <p>{preview.before.duplicate_rows} duplicate rows</p>
            </div>

            <div className="comparison-card after-card">
              <span>After</span>
              <strong>{preview.after.rows}</strong>
              <small>Rows</small>
              <p>{preview.after.missing_values} missing values</p>
              <p>{preview.after.duplicate_rows} duplicate rows</p>
            </div>
          </div>

          <div className="detail-card">
            <h3>Changes made</h3>

            {Object.keys(preview.changes || {}).length > 0 ? (
              <div className="cleaning-changes">
                {Object.entries(preview.changes).map(([name, value]) => (
                  <div className="detail-row" key={name}>
                    <span>{name.replaceAll("_", " ")}</span>
                    <strong>{formatChange(value)}</strong>
                  </div>
                ))}
              </div>
            ) : (
              <p>No changes were made with the selected options.</p>
            )}
          </div>

          {preview.preview?.length > 0 && (
            <div className="detail-card">
              <h3>Cleaned data preview</h3>

              <div className="table-scroll">
                <table className="dataset-table">
                  <thead>
                    <tr>
                      {Object.keys(preview.preview[0]).map((key) => (
                        <th key={key}>{key}</th>
                      ))}
                    </tr>
                  </thead>

                  <tbody>
                    {preview.preview.map((row, index) => (
                      <tr key={index}>
                        {Object.keys(preview.preview[0]).map((key) => (
                          <td key={key}>
                            {row[key] === null || row[key] === undefined
                              ? "—"
                              : String(row[key])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="cleaning-buttons">
            <button
              className="primary-button"
              type="button"
              onClick={handleApplyCleaning}
              disabled={applying || cleanedReady || loading || downloading}
            >
              {applying ? (
                <>
                  <RefreshCw size={17} className="spin-icon" />
                  Applying cleaning...
                </>
              ) : cleanedReady ? (
                <>
                  <CheckCircle2 size={17} />
                  Cleaning applied
                </>
              ) : (
                <>
                  <WandSparkles size={17} />
                  Apply cleaning
                </>
              )}
            </button>

            <button
              className="primary-button download-cleaned-button"
              type="button"
              onClick={handleDownload}
              disabled={downloading || !cleanedReady || applying}
            >
              <Download size={18} />
              {downloading
                ? "Preparing download..."
                : "Download cleaned CSV"}
            </button>

            <button
              className="primary-button download-cleaned-button"
              type="button"
              onClick={handleExportExcel}
              disabled={exporting || !cleanedReady || applying}
              title="Cleaned data plus a sheet listing every change"
            >
              <FileSpreadsheet size={18} />
              {exporting ? "Preparing Excel..." : "Download Excel (with change log)"}
            </button>
          </div>

          {cleanedReady && (
            <p className="cleaning-note">
              Your cleaned dataset is saved. See the cleaning report below, then
              open Charts or AI Questions.
            </p>
          )}
        </div>
      )}
    </section>
  );
}

export default CleaningSection;
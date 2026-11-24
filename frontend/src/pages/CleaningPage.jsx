import { useOutletContext } from "react-router-dom";
import CleaningSection from "../components/CleaningSection";
import CleaningReport from "../components/CleaningReport";

function CleaningPage() {
  const dataset = useOutletContext();

  return (
    <div className="workspace-page">
      <CleaningSection
        datasetId={dataset.dataset_id}
        profile={dataset.profile}
        qualityReport={dataset.quality_report}
      />

      <CleaningReport datasetId={dataset.dataset_id} />
    </div>
  );
}

export default CleaningPage;
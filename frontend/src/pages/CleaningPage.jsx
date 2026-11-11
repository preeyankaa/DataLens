
import { useOutletContext } from "react-router-dom";
import CleaningSection from "../components/CleaningSection";

function CleaningPage() {
  const dataset = useOutletContext();

  return (
    <div className="workspace-page">
      <CleaningSection
        datasetId={dataset.dataset_id}
        profile={dataset.profile}
      />
    </div>
  );
}

export default CleaningPage;

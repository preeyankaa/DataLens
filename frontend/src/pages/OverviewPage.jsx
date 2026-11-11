
import { useOutletContext } from "react-router-dom";
import DatasetOverview from "../components/DatasetOverview";

function OverviewPage() {
  const dataset = useOutletContext();

  return (
    <div className="workspace-page">
      <DatasetOverview profile={dataset.profile} />
    </div>
  );
}

export default OverviewPage;

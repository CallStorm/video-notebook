import { Navigate } from "react-router-dom";

/** 集合已下线，统一跳回首页标签筛选。 */
export default function CollectionPage() {
  return <Navigate to="/" replace />;
}

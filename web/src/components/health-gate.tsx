import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface Health {
  status: "ok" | string;
  db?: string;
}

async function fetchHealth(): Promise<Health> {
  return api<Health>("/health/ready");
}

export function HealthGate() {
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 5_000,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>API 健康检查</CardTitle>
        <CardDescription>每 5 秒刷一次。验证 api → mysql 链路。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && <p className="text-sm text-muted-foreground">查询中…</p>}
        {data && (
          <div className="space-y-1 text-sm">
            <p>
              <span className="text-muted-foreground">status:</span>{" "}
              <span className="font-mono">{data.status}</span>
            </p>
            <p>
              <span className="text-muted-foreground">db:</span>{" "}
              <span className="font-mono">{data.db ?? "—"}</span>
            </p>
          </div>
        )}
        {error && (
          <div className="space-y-2">
            <p className="text-sm text-destructive">
              错误：{error instanceof ApiError ? `${error.code}: ${error.message}` : String(error)}
            </p>
            <Button onClick={() => refetch()} disabled={isFetching} variant="outline" size="sm">
              重试
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

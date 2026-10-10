import { ArrowLeft } from "lucide-react";

import { PageContainer, PageHeader } from "@/components/layout/PageHeader";
import { ButtonLink } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { NotFoundState } from "@/components/ui/States";

export function NotFoundPage() {
  return (
    <PageContainer>
      <PageHeader title="Page not found" breadcrumb={[{ label: "Overview", to: "/" }, { label: "Not found" }]} />
      <Card>
        <NotFoundState
          title="There is no page at this address."
          description="Check the link, or go back to your files."
          actions={
            <ButtonLink to="/files" icon={ArrowLeft}>
              Back to Files
            </ButtonLink>
          }
        />
      </Card>
    </PageContainer>
  );
}

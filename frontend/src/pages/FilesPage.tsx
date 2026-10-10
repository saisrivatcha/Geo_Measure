import { SearchX, Upload } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Pagination } from "@/components/data/Pagination";
import { PageContainer, PageHeader } from "@/components/layout/PageHeader";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { FileFilters, SORT_OPTIONS, type FileFilterValues } from "@/features/files/FileFilters";
import { FilesTable } from "@/features/files/FilesTable";
import { useFiles } from "@/hooks/queries";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import type { FileStatus, FileType } from "@/types/api";

const PAGE_SIZES = [20, 50, 100];

/** Filters, sort and paging live in the URL so views can be shared and survive reloads. */
export function FilesPage() {
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get("page")) || 1);
  const pageSize = PAGE_SIZES.includes(Number(params.get("page_size"))) ? Number(params.get("page_size")) : 20;
  const sortKey = SORT_OPTIONS.some((o) => o.value === params.get("sort")) ? (params.get("sort") as string) : "newest";
  const sort = SORT_OPTIONS.find((o) => o.value === sortKey) ?? SORT_OPTIONS[0]!;
  const type = (params.get("type") ?? "") as FileType | "";
  const status = (params.get("status") ?? "") as FileStatus | "";

  // The search box updates immediately; the query waits for typing to pause.
  const [search, setSearch] = useState(params.get("q") ?? "");
  const debouncedSearch = useDebouncedValue(search.trim(), 300);

  const update = (changes: Record<string, string | number | null>) => {
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        for (const [key, value] of Object.entries(changes)) {
          if (value === null || value === "" || value === undefined) next.delete(key);
          else next.set(key, String(value));
        }
        return next;
      },
      { replace: true },
    );
  };

  useEffect(() => {
    if ((params.get("q") ?? "") !== debouncedSearch) update({ q: debouncedSearch || null, page: null });
  }, [debouncedSearch]);

  const files = useFiles({
    page,
    page_size: pageSize,
    sort: sort.sort,
    order: sort.order,
    file_type: type || undefined,
    status: status || undefined,
    q: debouncedSearch || undefined,
  });

  const filtered = Boolean(debouncedSearch || type || status);
  const values: FileFilterValues = { q: search, type, status, sort: sortKey };

  const onFilterChange = (changes: Partial<FileFilterValues>) => {
    if (changes.q !== undefined) {
      setSearch(changes.q);
      return;
    }
    update({
      ...(changes.type !== undefined ? { type: changes.type || null } : {}),
      ...(changes.status !== undefined ? { status: changes.status || null } : {}),
      ...(changes.sort !== undefined ? { sort: changes.sort === "newest" ? null : changes.sort } : {}),
      page: null,
    });
  };

  const clearFilters = () => {
    setSearch("");
    setParams({}, { replace: true });
  };

  return (
    <PageContainer>
      <PageHeader
        title="Files"
        description="Manage uploaded geospatial datasets."
        breadcrumb={[{ label: "Overview", to: "/" }, { label: "Files" }]}
        actions={
          <ButtonLink to="/files/upload" variant="primary" icon={Upload}>
            Upload dataset
          </ButtonLink>
        }
      />

      <Card flush>
        <FileFilters values={values} onChange={onFilterChange} />
        {files.isError ? (
          <ErrorState title="Unable to load files." error={files.error} onRetry={() => files.refetch()} />
        ) : (
          <>
            <FilesTable
              caption="Uploaded files"
              files={files.data?.items}
              isLoading={files.isPending}
              isFetching={files.isFetching && !files.isPending}
              columns={["file", "type", "features", "sourceCrs", "measurementCrs", "status", "uploaded", "actions"]}
              empty={
                files.data && files.data.total > 0 ? (
                  <EmptyState
                    title="This page is empty."
                    description={`There are ${files.data.total} matching files; this page is past the last one.`}
                    actions={<Button onClick={() => update({ page: null })}>Go to first page</Button>}
                  />
                ) : filtered ? (
                  <EmptyState
                    icon={SearchX}
                    title="No files match these filters."
                    description="Try a different name, type or status."
                    actions={<Button onClick={clearFilters}>Clear filters</Button>}
                  />
                ) : (
                  <EmptyState
                    title="No geospatial files yet."
                    description="Upload a KML file or a zipped Shapefile to measure its features."
                    actions={
                      <ButtonLink to="/files/upload" variant="primary" icon={Upload}>
                        Upload your first dataset
                      </ButtonLink>
                    }
                  />
                )
              }
            />
            {files.data && files.data.total > 0 && (
              <Pagination
                page={page}
                pageSize={pageSize}
                total={files.data.total}
                pageSizeOptions={PAGE_SIZES}
                itemLabel="files"
                onPageChange={(next) => update({ page: next === 1 ? null : next })}
                onPageSizeChange={(size) => update({ page_size: size === 20 ? null : size, page: null })}
              />
            )}
          </>
        )}
      </Card>
    </PageContainer>
  );
}

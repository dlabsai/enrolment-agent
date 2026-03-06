import {
    type CellContext,
    type ColumnDef,
    flexRender,
    getCoreRowModel,
    getPaginationRowModel,
    getSortedRowModel,
    type OnChangeFn,
    type PaginationState,
    type SortingState,
    type Table as TableType,
    useReactTable,
} from "@tanstack/react-table";
import { Button } from "@va/shared/components/ui/button";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@va/shared/components/ui/select";
import { Skeleton } from "@va/shared/components/ui/skeleton";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@va/shared/components/ui/table";
import { cn } from "@va/shared/lib/utils";
import {
    ArrowDown,
    ArrowUp,
    ArrowUpDown,
    ChevronLeft,
    ChevronRight,
    ChevronsLeft,
    ChevronsRight,
} from "lucide-react";
import { createElement, type JSX } from "react";

type ColumnSkeleton<TData, TValue> =
    | JSX.Element
    | ((context: CellContext<TData, TValue>) => JSX.Element);

interface ColumnMeta<TData, TValue> {
    skeleton?: ColumnSkeleton<TData, TValue>;
}

interface DataTablePaginationProps<TData> {
    table: TableType<TData>;
}

const DataTablePagination = <TData,>({
    table,
}: DataTablePaginationProps<TData>): JSX.Element => (
    <div className="flex flex-col items-center justify-between gap-3 sm:flex-row">
        <div className="text-muted-foreground text-sm">
            Page {table.getState().pagination.pageIndex + 1} of{" "}
            {table.getPageCount()}
        </div>
        <div className="flex items-center gap-2">
            <Select
                onValueChange={(value) => {
                    table.setPageSize(Number(value));
                }}
                value={String(table.getState().pagination.pageSize)}
            >
                <SelectTrigger className="h-8 w-[110px]">
                    <SelectValue placeholder="Rows" />
                </SelectTrigger>
                <SelectContent side="top">
                    {[10, 20, 30, 40, 50].map((pageSize) => (
                        <SelectItem
                            key={pageSize}
                            value={String(pageSize)}
                        >
                            {pageSize} rows
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
            <div className="flex items-center gap-1">
                <Button
                    className="h-8 w-8 p-0"
                    disabled={!table.getCanPreviousPage()}
                    onClick={() => {
                        table.setPageIndex(0);
                    }}
                    size="icon-sm"
                    variant="outline"
                >
                    <ChevronsLeft className="size-4" />
                </Button>
                <Button
                    className="h-8 w-8 p-0"
                    disabled={!table.getCanPreviousPage()}
                    onClick={() => {
                        table.previousPage();
                    }}
                    size="icon-sm"
                    variant="outline"
                >
                    <ChevronLeft className="size-4" />
                </Button>
                <Button
                    className="h-8 w-8 p-0"
                    disabled={!table.getCanNextPage()}
                    onClick={() => {
                        table.nextPage();
                    }}
                    size="icon-sm"
                    variant="outline"
                >
                    <ChevronRight className="size-4" />
                </Button>
                <Button
                    className="h-8 w-8 p-0"
                    disabled={!table.getCanNextPage()}
                    onClick={() => {
                        table.setPageIndex(table.getPageCount() - 1);
                    }}
                    size="icon-sm"
                    variant="outline"
                >
                    <ChevronsRight className="size-4" />
                </Button>
            </div>
        </div>
    </div>
);

interface DataTableProps<TData, TValue> {
    columns: ColumnDef<TData, TValue>[];
    data: TData[];
    sorting: SortingState;
    onSortingChange: OnChangeFn<SortingState>;
    pagination: PaginationState;
    onPaginationChange: OnChangeFn<PaginationState>;
    pageCount: number;
    manualPagination?: boolean;
    manualSorting?: boolean;
    emptyMessage?: string;
    isLoading?: boolean;
    onRowClick?: (row: TData) => void;
    isRowSelected?: (row: TData) => boolean;
}

export const DataTable = <TData, TValue>({
    columns,
    data,
    sorting,
    onSortingChange,
    pagination,
    onPaginationChange,
    pageCount,
    manualPagination = true,
    manualSorting = true,
    emptyMessage = "No results.",
    isLoading = false,
    onRowClick,
    isRowSelected,
}: DataTableProps<TData, TValue>): JSX.Element => {
    // eslint-disable-next-line react-hooks/incompatible-library
    const table = useReactTable({
        data,
        columns,
        getCoreRowModel: getCoreRowModel(),
        getPaginationRowModel: getPaginationRowModel(),
        getSortedRowModel: getSortedRowModel(),
        onSortingChange,
        onPaginationChange,
        manualPagination,
        manualSorting,
        pageCount,
        state: {
            sorting,
            pagination,
        },
    });

    const columnCount = table.getAllLeafColumns().length;
    const { rows } = table.getRowModel();

    let bodyContent: JSX.Element | JSX.Element[] = (
        <TableRow>
            <TableCell
                className="py-10 text-center text-sm"
                colSpan={columnCount}
            >
                {emptyMessage}
            </TableCell>
        </TableRow>
    );
    if (isLoading) {
        if (rows.length > 0) {
            bodyContent = rows.map((row) => (
                <TableRow
                    data-state={undefined}
                    key={row.id}
                >
                    {row.getVisibleCells().map((cell) => {
                        const skeletonMeta = cell.column.columnDef.meta as
                            | ColumnMeta<TData, TValue>
                            | undefined;
                        const skeleton = skeletonMeta?.skeleton;
                        const skeletonContent =
                            typeof skeleton === "function"
                                ? skeleton(cell.getContext())
                                : (skeleton ?? (
                                      <Skeleton className="h-5 w-full" />
                                  ));
                        return (
                            <TableCell key={cell.id}>
                                <div className="relative">
                                    <div className="invisible">
                                        {flexRender(
                                            cell.column.columnDef.cell,
                                            cell.getContext(),
                                        )}
                                    </div>
                                    <div
                                        aria-hidden="true"
                                        className="absolute inset-0 flex items-center"
                                    >
                                        {skeletonContent}
                                    </div>
                                </div>
                            </TableCell>
                        );
                    })}
                </TableRow>
            ));
        } else {
            const skeletonRowCount = pagination.pageSize;
            bodyContent = Array.from(
                { length: skeletonRowCount },
                (_unused, rowIndex) => (
                    <TableRow key={`skeleton-${rowIndex}`}>
                        {table.getAllLeafColumns().map((column) => {
                            const skeletonMeta = column.columnDef.meta as
                                | ColumnMeta<TData, TValue>
                                | undefined;
                            const skeleton = skeletonMeta?.skeleton;
                            return (
                                <TableCell key={column.id}>
                                    {typeof skeleton === "function" ? (
                                        <Skeleton className="h-5 w-full" />
                                    ) : (
                                        (skeleton ?? (
                                            <Skeleton className="h-5 w-full" />
                                        ))
                                    )}
                                </TableCell>
                            );
                        })}
                    </TableRow>
                ),
            );
        }
    } else if (rows.length > 0) {
        bodyContent = rows.map((row) => {
            const selected =
                isRowSelected?.(row.original) ?? row.getIsSelected();
            return (
                <TableRow
                    className={cn(
                        onRowClick && "hover:bg-muted/60 cursor-pointer",
                    )}
                    data-state={selected && "selected"}
                    key={row.id}
                    onClick={() => {
                        onRowClick?.(row.original);
                    }}
                >
                    {row.getVisibleCells().map((cell) => (
                        <TableCell key={cell.id}>
                            {flexRender(
                                cell.column.columnDef.cell,
                                cell.getContext(),
                            )}
                        </TableCell>
                    ))}
                </TableRow>
            );
        });
    }

    return (
        <div className="flex min-h-0 flex-1 flex-col gap-3">
            <div className="border-border flex min-h-0 flex-1 flex-col overflow-auto rounded-md border">
                <Table>
                    <TableHeader className="bg-background sticky top-0 z-10">
                        {table.getHeaderGroups().map((headerGroup) => (
                            <TableRow key={headerGroup.id}>
                                {headerGroup.headers.map((header) => {
                                    if (header.isPlaceholder) {
                                        return (
                                            <TableHead
                                                className="bg-background sticky top-0 z-10"
                                                key={header.id}
                                            />
                                        );
                                    }

                                    const canSort = header.column.getCanSort();
                                    const sortState =
                                        header.column.getIsSorted();
                                    let sortIcon = ArrowUpDown;
                                    if (sortState === "asc") {
                                        sortIcon = ArrowUp;
                                    } else if (sortState === "desc") {
                                        sortIcon = ArrowDown;
                                    }

                                    return (
                                        <TableHead
                                            className="bg-background sticky top-0 z-10"
                                            key={header.id}
                                        >
                                            {canSort ? (
                                                <button
                                                    className="hover:text-foreground inline-flex items-center gap-2 text-sm font-medium transition"
                                                    onClick={header.column.getToggleSortingHandler()}
                                                    type="button"
                                                >
                                                    {flexRender(
                                                        header.column.columnDef
                                                            .header,
                                                        header.getContext(),
                                                    )}
                                                    {createElement(sortIcon, {
                                                        className:
                                                            "text-muted-foreground size-3",
                                                    })}
                                                </button>
                                            ) : (
                                                flexRender(
                                                    header.column.columnDef
                                                        .header,
                                                    header.getContext(),
                                                )
                                            )}
                                        </TableHead>
                                    );
                                })}
                            </TableRow>
                        ))}
                    </TableHeader>
                    <TableBody>{bodyContent}</TableBody>
                </Table>
            </div>
            <div className="shrink-0">
                <DataTablePagination table={table} />
            </div>
        </div>
    );
};

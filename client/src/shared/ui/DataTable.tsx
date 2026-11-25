import type { ReactNode } from 'react'

export type DataTableColumn<Row> = {
  header: ReactNode
  id: string
  render: (row: Row) => ReactNode
}

type DataTableProps<Row> = {
  columns: DataTableColumn<Row>[]
  rows: Row[]
  getRowKey: (row: Row) => string | number
  caption?: string
  emptyMessage?: string
}

export function DataTable<Row>({ columns, rows, getRowKey, caption, emptyMessage = 'Không có dữ liệu để hiển thị.' }: DataTableProps<Row>) {
  return <div className="ui-data-table-wrapper">
    <table className="ui-data-table">
      {caption && <caption className="visually-hidden">{caption}</caption>}
      <thead><tr>{columns.map((column) => <th key={column.id} scope="col">{column.header}</th>)}</tr></thead>
      <tbody>
        {rows.length > 0
          ? rows.map((row) => <tr key={getRowKey(row)}>{columns.map((column) => <td key={column.id}>{column.render(row)}</td>)}</tr>)
          : <tr><td className="ui-data-table__empty" colSpan={columns.length}>{emptyMessage}</td></tr>}
      </tbody>
    </table>
  </div>
}

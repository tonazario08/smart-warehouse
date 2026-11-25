export type MovementType = 'inbound' | 'outbound'
export type MovementRow = { id:number; type:MovementType; warehouseId:number; productId:number; productName:string; sku:string; warehouseName:string; quantity:number; unit:string }
export function buildMovementRows({ transactions, products, warehouses }: { transactions:{id:number;transaction_type:MovementType;warehouse_id:number;product_id:number;quantity:number}[]; products:{id:number;sku:string;name:string;unit:string}[]; warehouses:{id:number;code:string;name:string}[] }): MovementRow[] {
  const productMap=new Map(products.map(item=>[item.id,item])); const warehouseMap=new Map(warehouses.map(item=>[item.id,item]))
  return transactions.flatMap(item=>{ const product=productMap.get(item.product_id); const warehouse=warehouseMap.get(item.warehouse_id); return product&&warehouse?[{id:item.id,type:item.transaction_type,warehouseId:item.warehouse_id,productId:item.product_id,productName:product.name,sku:product.sku,warehouseName:warehouse.name,quantity:item.quantity,unit:product.unit}]:[] }).sort((a,b)=>b.id-a.id)
}
export function filterMovementRows(rows:MovementRow[],{search,type}:{search:string;type:MovementType}) { const query=search.trim().toLocaleLowerCase('vi'); return rows.filter(row=>row.type===type&&(!query||`${row.sku} ${row.productName} ${row.warehouseName}`.toLocaleLowerCase('vi').includes(query))) }

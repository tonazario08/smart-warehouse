type SearchableProduct = {
  category_id: number
  name: string
  sku: string
}

export function filterProducts<T extends SearchableProduct>(products: T[], { categoryId, search }: { categoryId: number | null; search: string }) {
  const query = search.trim().toLocaleLowerCase('vi')
  return products.filter((product) => {
    const matchesCategory = categoryId === null || product.category_id === categoryId
    const matchesSearch = query === '' || `${product.sku} ${product.name}`.toLocaleLowerCase('vi').includes(query)
    return matchesCategory && matchesSearch
  })
}

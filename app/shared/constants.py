# 默认分页大小，避免列表接口一次返回过多数据。
DEFAULT_PAGE_SIZE = 20

# 默认分页页码，对外 query 参数统一使用 pageNum。
DEFAULT_PAGE_NUM = 1

# 分页大小上限，防止滥用接口造成数据库压力。
MAX_PAGE_SIZE = 100

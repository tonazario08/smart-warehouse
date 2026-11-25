const { ApiError } = require('../src/api')

const error = new ApiError('Unauthorized', 401)

if (error.status !== 401) {
  throw new Error('ApiError must preserve the HTTP status so auth cleanup can distinguish 401 from transient failures.')
}

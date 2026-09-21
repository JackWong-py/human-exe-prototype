import { useCallback, useEffect, useState } from "react"

// A tiny helper: call `load()` when the page opens and keep three things for you:
//   data (the answer), error (if it failed), loading (true while waiting).
// `reload()` asks again. Pass a list of values in `deps` if `load` uses them.
export function useApi(load, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true })

  const reload = useCallback(() => {
    setState((previous) => ({ ...previous, loading: true, error: null }))
    load()
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((error) => setState({ data: null, error, loading: false }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    reload()
  }, [reload])

  return { ...state, reload }
}

function build(state) {
  var saved = state.saved || [], used = {}, rows = []
  var failures = {}
  ;(state.last_restore || []).forEach(function(r) { if (r.error || r.layout_error) failures[r.id] = r.error || r.layout_error })
  ;(state.windows || []).forEach(function(w) {
    var record = saved.find(function(r) { return !used[r.id] && r.key === w.key })
    if (!record && w.recipe && w.recipe.identity)
      record = saved.find(function(r) { return !used[r.id] && r.recipe.identity === w.recipe.identity })
    if (record) used[record.id] = true
    var changed = !!record && (record.blocked || w.status === 'changed')
    var needsAdapter = !!(w.recipe && w.recipe.needs_adapter)
    var undecided = !!w.recipe && !w.error && (!record || needsAdapter) && !(state.skipped || {})[w.key]
    rows.push({workspace: String(w.placement.workspace), group: w.placement.group || null, address: w.address, key: w.key, uid: w.key,
      id: record ? record.id : '', saved: !!record && !needsAdapter, needsAdapter: needsAdapter, app: w.app || '', desktopId: w.recipe && w.recipe.state ? w.recipe.state.desktop_id || '' : '',
      eligible: !!w.recipe && !w.error && !needsAdapter, undecided: undecided, dirty: undecided,
      error: w.error || (changed ? 'Current recovery state is unavailable.' : ''), label: w.recipe ? w.recipe.label : w.app,
      title: w.title, detail: w.error || (w.recipe ? w.recipe.detail : 'Recovery is not supported for this window.'),
      status: w.error ? 'Error' : changed ? 'Changed' : record ? 'Saved' : w.recipe ? 'Not saved' : 'Unsupported'})
  })
  saved.forEach(function(r) {
    if (used[r.id]) return
    rows.push({workspace: String(r.placement.workspace), group: r.placement.group || null, address: '', key: '', uid: r.id, id: r.id,
      saved: true, closed: true, eligible: true, undecided: false, dirty: false, app: r.app || '', desktopId: r.recipe.state ? r.recipe.state.desktop_id || '' : '',
      error: failures[r.id] || (r.blocked ? 'Recovery state is unavailable.' : ''), label: r.recipe.label, title: r.title,
      detail: failures[r.id] || ('Closed · ' + r.recipe.detail),
      status: failures[r.id] ? 'Error' : r.blocked ? 'Changed' : 'Closed · saved'})
  })
  var workspaces = Array.from(new Set(rows.map(function(r) { return r.workspace })))
  workspaces.sort(function(a, b) { return /^-?\d+$/.test(a) && /^-?\d+$/.test(b) ? Number(a) - Number(b) : a.localeCompare(b) })
  var groups = workspaces.map(function(ws) {
    var wsRows = rows.filter(function(r) { return r.workspace === ws })
    var ids = Array.from(new Set(wsRows.filter(r => r.group).map(r => r.group.id))).sort()
    wsRows.forEach(function(r) { r.groupLabel = r.group ? String(ids.indexOf(r.group.id) + 1) + ":" + String(r.group.index + 1) : "–" })
    wsRows.sort(function(a,b) {
      if (a.group && b.group) return a.group.id.localeCompare(b.group.id) || a.group.index - b.group.index
      return a.group ? -1 : b.group ? 1 : 0
    })
    return {workspace: ws, rows: wsRows}
  })
  return {groups: groups, rows: [].concat.apply([], groups.map(function(g) { return g.rows })), dirty: rows.some(function(r) { return r.dirty }), error: rows.some(function(r) { return !!r.error }), count: rows.length}
}

function primaryAction(row) {
  if (row.closed) return ["restore", "--id", row.id]
  if (row.needsAdapter) return ["create-adapter", "--address", row.address, "--key", row.key]
  if (row.saved) return ["forget", "--id", row.id]
  return ["persist", "--address", row.address]
}

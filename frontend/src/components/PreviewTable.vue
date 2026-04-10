<script setup>
defineProps({
  headers: {
    type: Array,
    required: true,
  },
  rows: {
    type: Array,
    required: true,
  },
});
</script>

<template>
  <div class="preview-shell">
    <div class="preview-heading">
      <strong>First {{ rows.length }} rows</strong>
      <span>{{ headers.length }} detected column(s)</span>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th v-for="header in headers" :key="header">{{ header }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in rows" :key="index">
            <td v-for="header in headers" :key="header">{{ row[header] }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.preview-shell {
  display: grid;
  gap: 10px;
}

.preview-heading {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--color-text-neutral-base);
  font-size: var(--text-content-text-bold-md);
  line-height: var(--text-content-text-bold-md--line-height);
  font-weight: var(--text-content-text-bold-md--font-weight);
}

.preview-heading span {
  color: var(--color-text-neutral-secondary);
}

.table-wrap {
  overflow-x: auto;
  border: 1px solid var(--color-borders-neutral-light);
  border-radius: 8px;
  background: var(--color-surface-neutral-100);
}

table {
  width: 100%;
  border-collapse: collapse;
}

th,
td {
  padding: 13px 14px;
  border-bottom: 1px solid var(--color-borders-neutral-light);
  text-align: left;
  white-space: nowrap;
}

th {
  background: var(--color-surface-neutral-200);
  color: var(--color-text-neutral-secondary);
  font-size: var(--text-content-legends-bold-md);
  line-height: var(--text-content-legends-bold-md--line-height);
  font-weight: var(--text-content-legends-bold-md--font-weight);
}

tbody tr:hover {
  background: var(--color-actions-neutral-hover-overlay);
}
</style>

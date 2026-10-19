import { useState } from 'react'
import {
  Alert,
  Box,
  Button,
  MenuItem,
  Paper,
  Select,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import { useDeleteUser, useMeta, useUpdateUser, useUsers } from '../api/hooks'
import { errorMessage } from '../api/client'
import type { Role, User } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { CreateUserDialog } from '../components/CreateUserDialog'
import { QueryState } from '../components/QueryState'
import { label } from '../lib/format'

export function UsersPage() {
  const { user: me } = useAuth()
  const usersQuery = useUsers()
  const { data: meta } = useMeta()
  const update = useUpdateUser()
  const remove = useDeleteUser()
  const [createOpen, setCreateOpen] = useState(false)
  const [toDelete, setToDelete] = useState<User | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const onError = (e: unknown) => setActionError(errorMessage(e))

  const changeRole = (u: User, role: Role) => {
    setActionError(null)
    update.mutate({ id: u.id, body: { role } }, { onError })
  }
  const toggleActive = (u: User, is_active: boolean) => {
    setActionError(null)
    update.mutate({ id: u.id, body: { is_active } }, { onError })
  }
  const confirmDelete = () => {
    if (!toDelete) return
    setActionError(null)
    // Backend rejects self-deletion with 400; its message is surfaced here.
    remove.mutate(toDelete.id, { onError })
    setToDelete(null)
  }

  return (
    <Stack spacing={2}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h4" component="h1">
          Users
        </Typography>
        <Button variant="contained" onClick={() => setCreateOpen(true)}>
          Create user
        </Button>
      </Box>
      {actionError && (
        <Alert severity="error" onClose={() => setActionError(null)}>
          {actionError}
        </Alert>
      )}
      <QueryState isPending={usersQuery.isPending} error={usersQuery.error} isEmpty={usersQuery.data?.length === 0} emptyText="No users.">
        <TableContainer component={Paper}>
          <Table aria-label="Users">
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Email</TableCell>
                <TableCell>Role</TableCell>
                <TableCell>Active</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {usersQuery.data?.map((u) => (
                <TableRow key={u.id}>
                  <TableCell>
                    {u.full_name}
                    {u.id === me?.id && ' (you)'}
                  </TableCell>
                  <TableCell>{u.email}</TableCell>
                  <TableCell>
                    <Select
                      size="small"
                      value={u.role}
                      onChange={(e) => changeRole(u, e.target.value)}
                      inputProps={{ 'aria-label': `Role for ${u.email}` }}
                    >
                      {(meta?.roles ?? [u.role]).map((r) => (
                        <MenuItem key={r} value={r}>
                          {label(r)}
                        </MenuItem>
                      ))}
                    </Select>
                  </TableCell>
                  <TableCell>
                    <Switch
                      checked={u.is_active}
                      onChange={(e) => toggleActive(u, e.target.checked)}
                      inputProps={{ 'aria-label': `Active: ${u.email}` }}
                    />
                  </TableCell>
                  <TableCell align="right">
                    <Button color="error" size="small" onClick={() => setToDelete(u)} aria-label={`Delete ${u.email}`}>
                      Delete
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </QueryState>

      <CreateUserDialog open={createOpen} roles={meta?.roles ?? ['admin', 'hr_manager', 'viewer']} onClose={() => setCreateOpen(false)} />
      <ConfirmDialog
        open={!!toDelete}
        title="Delete user?"
        message={`${toDelete?.email ?? 'This user'} will be permanently deleted.`}
        confirmLabel="Delete user"
        busy={remove.isPending}
        onConfirm={confirmDelete}
        onCancel={() => setToDelete(null)}
      />
    </Stack>
  )
}

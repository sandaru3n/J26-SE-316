import { useContext } from 'react'
import { DialogContext } from '../context/detailDialogContext.js'

/** The C2 full-detail popup, or null outside <DetailDialogProvider>. */
export function useDetailDialog() {
  return useContext(DialogContext)
}

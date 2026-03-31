import React from 'react'
import MirrorRenderer from '../runtime/MirrorRenderer.jsx'
import { pageData } from './generation.meta.js'

export default function AppBody({ selectedNodeId = '' }) {
 return <MirrorRenderer pageData={pageData} selectedNodeId={selectedNodeId} />
}

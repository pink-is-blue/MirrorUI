import React, { useEffect, useRef, useState } from 'react'

const VOID_TAGS = new Set(['img', 'input'])

function cleanStyleValue(value) {
  if (!value || value === 'normal' || value === 'auto' || value === 'none') {
    return undefined
  }
  return value
}

function buildStyle(node) {
  const { styles = {}, tag } = node
  const style = {
    display: cleanStyleValue(styles.display),
    position: cleanStyleValue(styles.position),
    visibility: cleanStyleValue(styles.visibility),
    pointerEvents: cleanStyleValue(styles.pointerEvents),
    color: cleanStyleValue(styles.color),
    backgroundColor: cleanStyleValue(styles.backgroundColor),
    backgroundImage: styles.backgroundImage && styles.backgroundImage !== 'none' ? styles.backgroundImage : undefined,
    backgroundPosition: cleanStyleValue(styles.backgroundPosition),
    backgroundSize: cleanStyleValue(styles.backgroundSize),
    backgroundRepeat: cleanStyleValue(styles.backgroundRepeat),
    width: cleanStyleValue(styles.width),
    height: cleanStyleValue(styles.height),
    minWidth: cleanStyleValue(styles.minWidth),
    minHeight: cleanStyleValue(styles.minHeight),
    maxWidth: cleanStyleValue(styles.maxWidth),
    maxHeight: cleanStyleValue(styles.maxHeight),
    fontSize: cleanStyleValue(styles.fontSize),
    fontWeight: cleanStyleValue(styles.fontWeight),
    fontFamily: cleanStyleValue(styles.fontFamily),
    lineHeight: cleanStyleValue(styles.lineHeight),
    letterSpacing: cleanStyleValue(styles.letterSpacing),
    textAlign: cleanStyleValue(styles.textAlign),
    textDecoration: cleanStyleValue(styles.textDecoration),
    textTransform: cleanStyleValue(styles.textTransform),
    borderRadius: cleanStyleValue(styles.borderRadius),
    borderWidth: cleanStyleValue(styles.borderWidth),
    borderStyle: cleanStyleValue(styles.borderStyle),
    borderColor: cleanStyleValue(styles.borderColor),
    boxShadow: styles.boxShadow && styles.boxShadow !== 'none' ? styles.boxShadow : undefined,
    marginTop: cleanStyleValue(styles.marginTop),
    marginRight: cleanStyleValue(styles.marginRight),
    marginBottom: cleanStyleValue(styles.marginBottom),
    marginLeft: cleanStyleValue(styles.marginLeft),
    paddingTop: cleanStyleValue(styles.paddingTop),
    paddingRight: cleanStyleValue(styles.paddingRight),
    paddingBottom: cleanStyleValue(styles.paddingBottom),
    paddingLeft: cleanStyleValue(styles.paddingLeft),
    gap: cleanStyleValue(styles.gap),
    rowGap: cleanStyleValue(styles.rowGap),
    columnGap: cleanStyleValue(styles.columnGap),
    justifyContent: cleanStyleValue(styles.justifyContent),
    alignItems: cleanStyleValue(styles.alignItems),
    alignSelf: cleanStyleValue(styles.alignSelf),
    gridTemplateColumns: cleanStyleValue(styles.gridTemplateColumns),
    gridTemplateRows: cleanStyleValue(styles.gridTemplateRows),
    gridColumn: cleanStyleValue(styles.gridColumn),
    gridRow: cleanStyleValue(styles.gridRow),
    flexDirection: cleanStyleValue(styles.flexDirection),
    flexWrap: cleanStyleValue(styles.flexWrap),
    flexGrow: cleanStyleValue(styles.flexGrow),
    flexShrink: cleanStyleValue(styles.flexShrink),
    flexBasis: cleanStyleValue(styles.flexBasis),
    opacity: cleanStyleValue(styles.opacity),
    overflow: cleanStyleValue(styles.overflow),
    overflowX: cleanStyleValue(styles.overflowX),
    overflowY: cleanStyleValue(styles.overflowY),
    left: cleanStyleValue(styles.left),
    top: cleanStyleValue(styles.top),
    right: cleanStyleValue(styles.right),
    bottom: cleanStyleValue(styles.bottom),
    objectFit: cleanStyleValue(styles.objectFit),
    zIndex: cleanStyleValue(styles.zIndex),
    boxSizing: 'border-box',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
  }

  if (!style.display) {
    style.display = tag === 'span' ? 'inline' : 'block'
  }

  if (tag === 'img') {
    style.objectFit = style.objectFit || 'cover'
  }

  return style
}

function renderText(node) {
  if (node.tag === 'input' || node.tag === 'textarea' || node.tag === 'select') {
    return null
  }
  return node.text || null
}

function MirrorNode({ node, selectedNodeId, isRoot = false }) {
  const Tag = node.tag || 'div'
  const attrs = { ...(node.attrs || {}) }
  const style = buildStyle(node)
  if (isRoot) {
    style.position = 'relative'
    style.marginTop = '0px'
    style.marginRight = '0px'
    style.marginBottom = '0px'
    style.marginLeft = '0px'
    style.width = '100%'
    style.minHeight = '100%'
  }
  const children = Array.isArray(node.children) ? node.children : []
  const className = [
    'mirror-node',
    selectedNodeId && selectedNodeId === node.node_id ? 'mirror-node-selected' : '',
  ]
    .filter(Boolean)
    .join(' ')

  const commonProps = {
    key: node.node_id,
    'data-mirror-id': node.node_id,
    className,
    style,
    title: node.node_id,
  }

  if (Tag === 'img') {
    return <img {...commonProps} src={attrs.src || ''} alt={attrs.alt || ''} />
  }

  if (Tag === 'input') {
    return <input {...commonProps} type={attrs.type || 'text'} defaultValue={attrs.value || ''} placeholder={attrs.placeholder || ''} readOnly />
  }

  if (Tag === 'textarea') {
    return <textarea {...commonProps} defaultValue={attrs.value || node.text || ''} placeholder={attrs.placeholder || ''} readOnly />
  }

  if (Tag === 'a') {
    return (
      <a {...commonProps} href={attrs.href || '#'}>
        {renderText(node)}
        {children.map((child) => (
          <MirrorNode key={child.node_id} node={child} selectedNodeId={selectedNodeId} />
        ))}
      </a>
    )
  }

  if (VOID_TAGS.has(Tag)) {
    return <Tag {...commonProps} />
  }

  return (
    <Tag {...commonProps}>
      {renderText(node)}
      {children.map((child) => (
        <MirrorNode key={child.node_id} node={child} selectedNodeId={selectedNodeId} />
      ))}
    </Tag>
  )
}

export default function MirrorRenderer({ pageData, selectedNodeId = '', showReferenceOverlay = true, referenceOpacity = 0.08 }) {
  const frameRef = useRef(null)
  const [scale, setScale] = useState(1)

  const pageWidth = Math.max(pageData?.width || 1440, 320)
  const pageHeight = Math.max(pageData?.height || 900, 200)

  useEffect(() => {
    if (!frameRef.current) return
    const obs = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (!entry) return
      const containerWidth = entry.contentRect.width
      if (containerWidth > 0) {
        setScale(containerWidth / pageWidth)
      }
    })
    obs.observe(frameRef.current)
    return () => obs.disconnect()
  }, [pageWidth])

  if (!pageData?.root) {
    return null
  }

  return (
    <div className="mirror-stage">
      <div className="mirror-frame" ref={frameRef}>
        {/* Outer wrapper collapses to the scaled height so the parent flow is correct */}
        <div style={{ width: '100%', height: `${Math.round(pageHeight * scale)}px`, overflow: 'hidden', position: 'relative' }}>
          <div
            className="mirror-canvas"
            style={{
              width: `${pageWidth}px`,
              minHeight: `${pageHeight}px`,
              backgroundColor: pageData.backgroundColor || 'rgb(255, 255, 255)',
              transformOrigin: 'top left',
              transform: `scale(${scale})`,
              position: 'relative',
            }}
          >
            {pageData.screenshotUrl && showReferenceOverlay ? (
              <img
                className="mirror-reference"
                src={pageData.screenshotUrl}
                alt=""
                aria-hidden="true"
                style={{ opacity: referenceOpacity, width: '100%', height: '100%' }}
              />
            ) : null}
            <MirrorNode node={pageData.root} selectedNodeId={selectedNodeId} isRoot />
          </div>
        </div>
      </div>
    </div>
  )
}
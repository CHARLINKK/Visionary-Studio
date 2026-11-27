import React from 'react';

// Safe attribute sanitizer to avoid React unknown DOM prop warnings
const sanitizeProps = (props) => {
  const {
    children,
    id,
    className,
    style,
    onClick,
    onDblClick,
    onMouseDown,
    onMouseUp,
    text,
    draggable,
    ..._rest
  } = props;
  return {
    domProps: {
      ...(id ? { id } : {}),
      ...(className ? { className } : {}),
      ...(style ? { style } : {}),
      ...(onClick ? { onClick } : {}),
      ...(onDblClick ? { onDoubleClick: onDblClick } : {}),
      ...(onMouseDown ? { onMouseDown } : {}),
      ...(onMouseUp ? { onMouseUp } : {}),
      ...(props.onContextMenu
        ? {
            onContextMenu: (e) =>
              props.onContextMenu({
                evt: e,
                cancelBubble: false,
                target: e.target,
              }),
          }
        : {}),
      ...(draggable !== undefined ? { 'data-draggable': String(Boolean(draggable)) } : {}),
    },
    text,
    draggable,
    children,
  };
};

export const Stage = (props) => {
  const { domProps, children } = sanitizeProps(props);
  return (
    <div data-testid="konva-stage" {...domProps}>
      {children}
    </div>
  );
};

export const Layer = (props) => {
  const { domProps, children } = sanitizeProps(props);
  return (
    <div data-testid="konva-layer" {...domProps}>
      {children}
    </div>
  );
};

export const Group = (props) => {
  const { domProps, children } = sanitizeProps(props);
  return (
    <div data-testid="konva-group" {...domProps}>
      {children}
    </div>
  );
};

export const Rect = (props) => {
  const { domProps } = sanitizeProps(props);
  return <div data-testid="konva-rect" {...domProps} />;
};

export const Text = (props) => {
  const { domProps, text } = sanitizeProps(props);
  return (
    <span data-testid="konva-text" {...domProps}>
      {text}
    </span>
  );
};

export const Path = (props) => {
  const { domProps } = sanitizeProps(props);
  return <svg data-testid="konva-path" {...domProps} />;
};

export const Image = (props) => {
  const { domProps } = sanitizeProps(props);
  return <img data-testid="konva-image" alt="konva-mock" {...domProps} />;
};

export const Line = (props) => {
  const { domProps } = sanitizeProps(props);
  return <div data-testid="konva-line" {...domProps} />;
};

export const Circle = (props) => {
  const { domProps } = sanitizeProps(props);
  return <div data-testid="konva-circle" {...domProps} />;
};

const ReactKonvaMock = {
  Stage,
  Layer,
  Group,
  Rect,
  Text,
  Path,
  Image,
  Line,
  Circle,
};

export default ReactKonvaMock;

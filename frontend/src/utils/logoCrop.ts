export const LOGO_OUTPUT_WIDTH = 600;
export const LOGO_OUTPUT_HEIGHT = 180;

export interface LogoPlacement {
  x: number;
  y: number;
  width: number;
  height: number;
}

export function logoPlacement(
  imageWidth: number,
  imageHeight: number,
  zoom: number,
  offsetX: number,
  offsetY: number,
): LogoPlacement {
  const safeWidth = Math.max(1, imageWidth);
  const safeHeight = Math.max(1, imageHeight);
  const scale = Math.max(LOGO_OUTPUT_WIDTH / safeWidth, LOGO_OUTPUT_HEIGHT / safeHeight) * Math.max(1, zoom);
  const width = safeWidth * scale;
  const height = safeHeight * scale;
  const overflowX = Math.max(0, width - LOGO_OUTPUT_WIDTH) / 2;
  const overflowY = Math.max(0, height - LOGO_OUTPUT_HEIGHT) / 2;
  return {
    x: (LOGO_OUTPUT_WIDTH - width) / 2 + overflowX * Math.max(-1, Math.min(1, offsetX / 100)),
    y: (LOGO_OUTPUT_HEIGHT - height) / 2 + overflowY * Math.max(-1, Math.min(1, offsetY / 100)),
    width,
    height,
  };
}

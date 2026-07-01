export const ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

export function validateImageFile(file: File): string | null {
  if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
    return "Choose a JPEG, PNG, or WebP image.";
  }

  if (file.size > MAX_UPLOAD_BYTES) {
    return "Choose an image smaller than 10 MB.";
  }

  return null;
}

/**
 * OpenAPI path/schema helpers.
 * Regenerate types with: npm run openapi:gen (API must be running on :8000).
 */
import type {components, paths} from "./generated/schema";

export type {components, paths};

/** JSON body for a successful (200) response on a path+method. */
export type ApiJsonOk<
  Path extends keyof paths,
  Method extends keyof paths[Path] & string,
> = paths[Path][Method] extends {
  responses: {200: {content: {"application/json": infer R}}};
}
  ? R
  : never;

/** JSON request body for a path+method (when present). */
export type ApiJsonBody<
  Path extends keyof paths,
  Method extends keyof paths[Path] & string,
> = paths[Path][Method] extends {
  requestBody: {content: {"application/json": infer B}};
}
  ? B
  : never;

export type Schemas = components["schemas"];

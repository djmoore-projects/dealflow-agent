// CSS Modules — every imported .module.css file is a Record of class name strings.
declare module "*.module.css" {
  const classes: Record<string, string>;
  export default classes;
}

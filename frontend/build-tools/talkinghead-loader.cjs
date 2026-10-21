// Turbopack cannot bundle TalkingHead's runtime-built `import(moduleName)` (its lip-sync loader).
// Mark it as a runtime import. It is never reached: the avatar registers English lip-sync itself
// and passes no modules (src/features/avatar). node_modules stays untouched.
module.exports = function talkingHeadLoader(source) {
  return source.replace("import(moduleName)", "import(/* turbopackIgnore: true */ /* webpackIgnore: true */ moduleName)");
};

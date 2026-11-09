import * as path from "path";
import {
  applyPatchesToBody,
  BytePatch,
  classIndexByName,
  disassemble,
  ensureBackup,
  methodIdxForTrait,
  parseAbc,
  parseSwf,
  PatchError,
  writeSwf,
  writeU30,
} from "./swfPatchUtils";

// When a dungeon boss is defeated, BossFight.method_1981 calls
// Room.CueKillAllMonsters(), which kills every monster still alive in the room.
// This patch turns that cue into a no-op so the remaining enemies stay alive
// after the boss dies (dungeon completion is still driven by the boss death).

const DEFAULT_SWF = path.resolve(
  __dirname,
  "..",
  "..",
  "client",
  "content",
  "localhost",
  "p",
  "cbp",
  "DungeonBlitz.swf",
);

const CLASS_NAME = "Room";
const METHOD_NAME = "CueKillAllMonsters";
const RETURNVOID = 0x47;

function parseArgs(argv: string[]): { swfPath: string; verify: boolean } {
  let swfPath = DEFAULT_SWF;
  let verify = false;

  for (let index = 2; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--swf" || arg === "-s") {
      swfPath = path.resolve(argv[++index] || "");
      continue;
    }
    if (arg === "--verify" || arg === "--dry-run") {
      verify = true;
      continue;
    }
    if (arg === "--help" || arg === "-h") {
      console.log([
        "Usage:",
        "  npx ts-node src/server/scripts/patch-dungeonblitz-no-boss-death-kill-all.ts [--verify] [--swf <path>]",
        "",
        "Makes Room.CueKillAllMonsters a no-op so remaining dungeon enemies",
        "do not die automatically when the boss is defeated.",
      ].join("\n"));
      process.exit(0);
    }

    throw new Error(`Unknown argument: ${arg}`);
  }

  return { swfPath, verify };
}

function patchSwf(swfPath: string, verify: boolean): void {
  const ctx = parseSwf(swfPath);
  const abc = parseAbc(ctx);
  const classIndex = classIndexByName(abc, CLASS_NAME);
  if (classIndex === null) {
    throw new PatchError(`Could not find ${CLASS_NAME} class.`);
  }

  const methodIdx = methodIdxForTrait(abc.instances[classIndex].traits, abc, METHOD_NAME);
  if (methodIdx === null) {
    throw new PatchError(`Could not find ${CLASS_NAME}.${METHOD_NAME}.`);
  }

  const methodBody = abc.methodBodies.get(methodIdx);
  if (!methodBody) {
    throw new PatchError(`Could not find method body for ${CLASS_NAME}.${METHOD_NAME} (${methodIdx}).`);
  }

  const code = ctx.body.subarray(methodBody.codeStart, methodBody.codeStart + methodBody.codeLen);
  const instructions = disassemble(code, `${CLASS_NAME}.${METHOD_NAME}`);
  if (instructions.length === 1 && instructions[0].opcode === RETURNVOID) {
    console.log(`${swfPath}: already patched (${CLASS_NAME}.${METHOD_NAME} is a no-op).`);
    return;
  }

  if (verify) {
    throw new PatchError(`${swfPath}: verify failed; ${CLASS_NAME}.${METHOD_NAME} still kills all monsters.`);
  }

  if (methodBody.exceptionCount > 0) {
    throw new PatchError(`${swfPath}: ${CLASS_NAME}.${METHOD_NAME} has an unexpected exception table.`);
  }

  const patchedCode = Buffer.from([RETURNVOID]);
  const patches: BytePatch[] = [
    {
      key: `${CLASS_NAME}.${METHOD_NAME}.code`,
      start: methodBody.codeStart,
      end: methodBody.codeStart + methodBody.codeLen,
      data: patchedCode,
      detail: "return immediately instead of killing every monster in the room",
    },
    {
      key: `${CLASS_NAME}.${METHOD_NAME}.codeLen`,
      start: methodBody.codeLenPos,
      end: methodBody.codeStart,
      data: writeU30(patchedCode.length),
      detail: `update ${CLASS_NAME}.${METHOD_NAME} code length`,
    },
  ];

  ensureBackup(swfPath);
  const { body, delta } = applyPatchesToBody(ctx.body, patches);
  writeSwf(ctx, body, delta);
  console.log(`${swfPath}: patched ${CLASS_NAME}.${METHOD_NAME} to a no-op.`);
}

const { swfPath, verify } = parseArgs(process.argv);
patchSwf(swfPath, verify);
